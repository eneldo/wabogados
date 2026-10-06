from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.deps import get_session as get_api_session
from app.core.config import get_settings
from app.db.session import get_session as get_db_session
from app.main import app
from app.middleware.audit import AuditLogMiddleware, SessionAdapter
from app.middleware.rate_limit import RateLimitMiddleware
from app.models import (
    Case,
    CaseLawyer,
    Client,
    Document,
    Lawyer,
    LegalArea,
    Permission,
    Role,
    User,
)
from app.security import create_access_token, hash_password
from app.security.permissions import (
    ROLE_DEFINITIONS,
    get_permission_definitions,
    get_permissions_for_role,
)
from app.services.documents import DocumentService
from app.services.media import MediaService
from app.services.messaging import MessagingService
from app.services.storage import StorageBackend
from app.services.storage_local import LocalStorage


def find_middleware[T](target: type[T]) -> T:
    """Return a live middleware instance, building the stack if needed."""
    if app.middleware_stack is None:
        app.middleware_stack = app.build_middleware_stack()

    node: object = app.middleware_stack
    while node is not None:
        if isinstance(node, target):
            return node
        node = getattr(node, "app", None)
    raise AssertionError(f"Middleware {target.__name__} not found in the stack")


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Iterator[RateLimitMiddleware]:
    """Keep the in-memory limiter isolated between tests."""
    limiter = find_middleware(RateLimitMiddleware)
    assert isinstance(limiter, RateLimitMiddleware)
    limiter.reset()
    yield limiter
    limiter.reset()


@pytest.fixture
def enabled_audit() -> Iterator[AuditLogMiddleware]:
    """Turn the audit middleware on for the duration of a test."""
    middleware = find_middleware(AuditLogMiddleware)
    assert isinstance(middleware, AuditLogMiddleware)
    previous = middleware.enabled
    middleware.enabled = True
    yield middleware
    middleware.enabled = previous


@pytest.fixture
def test_user() -> User:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email=f"test-{uuid4()}@example.com",
        full_name="Test User",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    return user


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Ephemeral engine so no test state leaks between runs."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def test_connection(test_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Outer transaction shared by every session used during a test."""
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest.fixture
async def database_session(test_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """Run each test in an outer transaction that is always rolled back.

    ``create_savepoint`` keeps application level ``commit`` calls scoped to a
    SAVEPOINT, so endpoints can commit real work while the test still
    discards everything at teardown.
    """
    session = AsyncSession(
        bind=test_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def session_factory(test_connection: AsyncConnection) -> Callable[[], AsyncSession]:
    """Factory for extra sessions bound to the same rolled back transaction.

    Used to exercise code that opens its own session, such as the bootstrap
    CLI, without escaping the per test isolation.
    """
    return partial(
        AsyncSession,
        bind=test_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture
async def test_user_in_db(test_user: User, database_session: AsyncSession) -> User:
    database_session.add(test_user)
    await database_session.flush()
    return test_user


@pytest.fixture
async def rbac_catalog(database_session: AsyncSession) -> dict[str, Role]:
    """Return the RBAC catalog, seeding only rows the migrations did not create."""
    existing_permissions = {
        permission.name: permission
        for permission in (await database_session.execute(select(Permission))).scalars()
    }
    for definition in get_permission_definitions():
        if definition.name in existing_permissions:
            continue
        permission = Permission(
            name=definition.name,
            resource=definition.resource,
            action=definition.action,
            description=definition.description,
        )
        database_session.add(permission)
        existing_permissions[definition.name] = permission
    await database_session.flush()

    catalog: dict[str, Role] = {}
    for role_name, description in ROLE_DEFINITIONS.items():
        result = await database_session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = result.scalar_one_or_none() or Role(name=role_name, description=description)
        if role not in database_session:
            database_session.add(role)
            await database_session.flush()
        catalog[role_name] = role

    for role_name in ROLE_DEFINITIONS:
        role = catalog[role_name]
        for permission_name in get_permissions_for_role(role_name):
            permission = existing_permissions[permission_name]
            if permission not in role.permissions:
                role.permissions.append(permission)
        await database_session.flush()

    return catalog


@pytest.fixture
async def admin_user(rbac_catalog: dict[str, Role], database_session: AsyncSession) -> User:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email=f"admin-{uuid4()}@example.com",
        full_name="Admin User",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    user.roles.append(rbac_catalog["administrador"])
    database_session.add(user)
    await database_session.flush()
    return user


@pytest.fixture
async def plain_user(rbac_catalog: dict[str, Role], database_session: AsyncSession) -> User:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email=f"plain-{uuid4()}@example.com",
        full_name="Plain User",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    user.roles.append(rbac_catalog["cliente"])
    database_session.add(user)
    await database_session.flush()
    return user


@pytest.fixture
async def staff_user(rbac_catalog: dict[str, Role], database_session: AsyncSession) -> User:
    """Abogado or asistente: read/create/update but never delete."""
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email=f"staff-{uuid4()}@example.com",
        full_name="Staff User",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    user.roles.append(rbac_catalog["abogado"])
    database_session.add(user)
    await database_session.flush()
    return user


@pytest.fixture
def staff_token(staff_user: User) -> str:
    return create_access_token(subject=staff_user.id)


@pytest.fixture
async def sample_case(
    database_session: AsyncSession, sample_client: Client, sample_lawyer: Lawyer
) -> Case:
    case = Case(
        case_number="WA-2026-000001",
        title="Expediente de prueba",
        client_id=sample_client.id,
        responsible_lawyer_id=sample_lawyer.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 1, 15),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()
    database_session.add(
        CaseLawyer(case_id=case.id, lawyer_id=sample_lawyer.id, role="responsable")
    )
    await database_session.flush()
    return case


@pytest.fixture
async def other_case(
    database_session: AsyncSession, sample_client: Client
) -> Case:
    """A case without any lawyer assignment, used to test access isolation."""
    case = Case(
        case_number="WA-2026-000002",
        title="Expediente ajeno",
        client_id=sample_client.id,
        process_type="penal",
        status="abierto",
        priority="alta",
        opened_at=date(2026, 2, 20),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()
    return case


@pytest.fixture
async def second_lawyer_token(
    database_session: AsyncSession, rbac_catalog: dict[str, Role]
) -> tuple[Lawyer, str]:
    """A lawyer role user linked to a lawyer record, with no assignments."""
    now = datetime.now(UTC)
    lawyer = Lawyer(
        document_type="DNI",
        document_number="11223344",
        full_name="Segundo Abogado",
        professional_card="CAL-22222",
        status="activo",
        is_active=True,
    )
    database_session.add(lawyer)
    user = User(
        id=uuid4(),
        email=f"lawyer2-{uuid4()}@example.com",
        full_name="Segundo Abogado",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    user.roles.append(rbac_catalog["abogado"])
    database_session.add(user)
    await database_session.flush()
    lawyer.user_id = user.id
    await database_session.flush()
    return lawyer, create_access_token(subject=user.id)


@pytest.fixture
def document_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalStorage:
    """A temporary storage backend shared by services and API endpoints.

    `DocumentService` is built inside the endpoints, so patching only the
    instances a test creates would let the endpoints write to the real
    configured root. This fixture injects the temporary root everywhere.
    """
    storage = LocalStorage(tmp_path)
    original_init = DocumentService.__init__

    def patched_init(
        self: DocumentService,
        session: AsyncSession,
        storage_override: StorageBackend | None = None,
    ) -> None:
        original_init(self, session, storage_override or storage)

    monkeypatch.setattr(DocumentService, "__init__", patched_init)
    return storage


@pytest.fixture
def message_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalStorage:
    """Temporary storage for message attachments, shared with the endpoints."""
    storage = LocalStorage(tmp_path)
    original_init = MessagingService.__init__

    def patched_init(
        self: MessagingService,
        session: AsyncSession,
        storage_override: StorageBackend | None = None,
    ) -> None:
        original_init(self, session, storage_override or storage)

    monkeypatch.setattr(MessagingService, "__init__", patched_init)
    return storage


@pytest.fixture
def media_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalStorage:
    """Temporary storage for the multimedia library, shared with the endpoints.

    `MediaService` is built inside the endpoints, so patching only the instances a
    test creates would let them write to the real configured root — and a test that
    stores a video must not leave one behind.
    """
    storage = LocalStorage(tmp_path)
    original_init = MediaService.__init__

    def patched_init(
        self: MediaService,
        session: AsyncSession,
        storage_override: StorageBackend | None = None,
    ) -> None:
        original_init(self, session, storage_override or storage)

    monkeypatch.setattr(MediaService, "__init__", patched_init)
    return storage


@pytest.fixture
async def sample_document(
    database_session: AsyncSession, sample_case: Case
) -> Document:
    document = Document(
        case_id=sample_case.id,
        document_type="contrato",
        title="Contrato de servicios",
        status="borrador",
        confidentiality="interno",
        visibility="interna",
        is_active=True,
    )
    database_session.add(document)
    await database_session.flush()
    return document


@pytest.fixture
async def second_lawyer_user(
    second_lawyer_token: tuple[Lawyer, str], database_session: AsyncSession
) -> tuple[User, str]:
    """The authenticated user behind `second_lawyer_token`, with no assignments."""
    lawyer, token = second_lawyer_token
    user = await database_session.get(User, lawyer.user_id)
    assert user is not None
    return user, token


@pytest.fixture
async def sample_client(database_session: AsyncSession) -> Client:
    client = Client(
        client_type="natural",
        document_type="DNI",
        document_number="12345678",
        full_name="Cliente de Prueba",
        email="cliente.prueba@wabogados.com",
        is_active=True,
    )
    database_session.add(client)
    await database_session.flush()
    return client


@pytest.fixture
async def legal_area(database_session: AsyncSession) -> LegalArea:
    """Return a seeded legal area, creating it only when the catalog lacks it."""
    result = await database_session.execute(
        select(LegalArea).where(LegalArea.name == "Civil")
    )
    area = result.scalar_one_or_none()
    if area is None:
        area = LegalArea(name="Civil", description="Derecho civil y obligaciones")
        database_session.add(area)
        await database_session.flush()
    return area


@pytest.fixture
async def sample_lawyer(
    database_session: AsyncSession, legal_area: LegalArea
) -> Lawyer:
    lawyer = Lawyer(
        document_type="DNI",
        document_number="87654321",
        full_name="Abogado de Prueba",
        professional_card="CAL-12345",
        email="abogado.prueba@wabogados.com",
        specialties=["Civil"],
        status="activo",
        is_active=True,
    )
    lawyer.legal_areas.append(legal_area)
    database_session.add(lawyer)
    await database_session.flush()
    return lawyer


@pytest.fixture
def user_token(test_user_in_db: User) -> str:
    return create_access_token(subject=test_user_in_db.id)


@pytest.fixture
async def portal_user(
    rbac_catalog: dict[str, Role], database_session: AsyncSession
) -> tuple[User, Client]:
    """A client portal identity linked to its own client record."""
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email=f"portal-{uuid4()}@example.com",
        full_name="Cliente Portal",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    user.roles.append(rbac_catalog["cliente"])
    database_session.add(user)
    await database_session.flush()

    client = Client(
        client_type="natural",
        document_type="DNI",
        document_number="55555555",
        full_name="Cliente Portal",
        is_active=True,
        user_id=user.id,
    )
    database_session.add(client)
    await database_session.flush()
    return user, client


@pytest.fixture
async def portal_case(
    database_session: AsyncSession,
    portal_user: tuple[User, Client],
) -> Case:
    """A case that belongs to the portal client's own identity.

    Needed by the tests that assert a client cannot see another client's case:
    `sample_case` belongs to a different client record.
    """
    _user, client = portal_user
    case = Case(
        case_number="WA-2026-000901",
        title="Expediente del cliente portal",
        client_id=client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 7, 1),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()
    return case


@pytest.fixture
def portal_token(portal_user: tuple[User, Client]) -> str:
    user, _client = portal_user
    return create_access_token(subject=user.id)


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token(subject=admin_user.id)


@pytest.fixture
def plain_user_token(plain_user: User) -> str:
    return create_access_token(subject=plain_user.id)


@pytest.fixture
def audit_in_test_transaction(
    database_session: AsyncSession,
) -> Iterator[AuditLogMiddleware]:
    """Enable auditing and let audit rows join the test transaction.

    Sharing the test session keeps the assertions honest (the real INSERT runs)
    while the outer rollback still discards the rows afterwards.
    """
    middleware = find_middleware(AuditLogMiddleware)
    assert isinstance(middleware, AuditLogMiddleware)
    previous_enabled = middleware.enabled
    previous_factory = middleware.session_factory
    middleware.enabled = True
    middleware.session_factory = lambda: SessionAdapter(database_session)
    yield middleware
    middleware.enabled = previous_enabled
    middleware.session_factory = previous_factory


@pytest.fixture
async def client(database_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield database_session

    app.dependency_overrides[get_api_session] = override_session
    app.dependency_overrides[get_db_session] = override_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as value:
            yield value
    finally:
        app.dependency_overrides.pop(get_api_session, None)
        app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
async def health_client() -> AsyncIterator[AsyncClient]:
    """Client for health checks with mocked database."""

    async def mock_session() -> AsyncIterator[AsyncSession]:
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        yield session

    app.dependency_overrides[get_db_session] = mock_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as value:
            yield value
    finally:
        app.dependency_overrides.pop(get_db_session, None)
