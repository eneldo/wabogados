from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_permission_names, get_user_role_names, require_permission
from app.middleware.audit import AuditLogMiddleware
from app.models import Permission, Role, User
from app.security import hash_password
from app.security.permissions import (
    ADMINISTRATOR_PERMISSIONS,
    get_permission_definitions,
    get_permissions_for_role,
    get_role_definitions,
)

AUTH = "/api/v1/admin"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_permission_matrix_covers_identity_surface() -> None:
    names = {definition.name for definition in get_permission_definitions()}

    assert "users:read" in names
    assert "users:assign_roles" in names
    assert "audit_logs:read" in names
    assert set(get_role_definitions()) == {"administrador", "abogado", "asistente", "cliente"}


def test_every_role_permission_exists_in_the_catalog() -> None:
    """A permission granted to a role but absent from the catalog is unsatisfiable.

    It fails quietly: the seeding migration inserts nothing and every login that
    depends on it gets a 403 with no obvious cause.
    """
    catalog = {definition.name for definition in get_permission_definitions()}
    orphans = {
        role_name: sorted(set(get_permissions_for_role(role_name)) - catalog)
        for role_name in get_role_definitions()
    }

    assert {role: names for role, names in orphans.items() if names} == {}


@pytest.mark.asyncio
async def test_every_catalog_permission_reaches_the_database(
    database_session: AsyncSession,
) -> None:
    """The catalog and the seeded rows must be the same set.

    `test_every_role_permission_exists_in_the_catalog` compares the matrix
    against the catalog, so it passed while `settings:read` was present in both
    and in neither migration. A permission can be perfectly consistent across the
    code and still absent from the database: every endpoint that requires it then
    answers 403 in production, and only the `rbac_catalog` fixture hides it by
    seeding the row itself.

    Deliberately does not depend on `rbac_catalog`, which would seed the missing
    rows and mask the whole point.
    """
    result = await database_session.execute(select(Permission.name))
    seeded = set(result.scalars().all())
    catalog = {definition.name for definition in get_permission_definitions()}

    assert not catalog - seeded, f"las migraciones no siembran: {sorted(catalog - seeded)}"


def test_permission_names_are_unique() -> None:
    names = [definition.name for definition in get_permission_definitions()]

    assert len(names) == len(set(names))


def test_administrator_holds_every_permission() -> None:
    assert set(ADMINISTRATOR_PERMISSIONS) == {
        definition.name for definition in get_permission_definitions()
    }
    assert set(get_permissions_for_role("administrador")) == set(ADMINISTRATOR_PERMISSIONS)


def test_operational_roles_have_resource_permissions() -> None:
    shared = {
        "clients:read",
        "clients:create",
        "clients:update",
        "lawyers:read",
        "legal_areas:read",
    }
    for role in ("abogado", "asistente"):
        assert shared <= set(get_permissions_for_role(role))


def test_case_scope_permissions_differ_by_role() -> None:
    abogado = set(get_permissions_for_role("abogado"))
    asistente = set(get_permissions_for_role("asistente"))

    assert "cases:read_assigned" in abogado
    assert "cases:read_all" not in abogado
    assert "cases:read_all" in asistente
    # Closing a case is a reserved legal act for administrators.
    assert "cases:close" not in abogado
    assert "cases:close" not in asistente
    assert "cases:close" in set(get_permissions_for_role("administrador"))


def test_operational_roles_cannot_delete() -> None:
    for role in ("abogado", "asistente", "cliente"):
        assert not any(
            permission.endswith(":delete") for permission in get_permissions_for_role(role)
        )


def test_client_role_only_sees_published_own_data() -> None:
    permissions = set(get_permissions_for_role("cliente"))

    assert permissions == {
        "actions:read_published",
        "calendar:read_published",
        "cases:read_published",
        "client_requests:read",
        "client_requests:respond",
        "dashboard:read",
        "documents:read_published",
        "evidences:download_optimized",
        "evidences:view_published",
        "messages:read",
        "messages:send",
        "notifications:read",
    }


async def test_permission_names_are_flattened(admin_user: User) -> None:
    assert get_user_role_names(admin_user) == ["administrador"]
    assert get_user_permission_names(admin_user) == set(ADMINISTRATOR_PERMISSIONS)


async def test_staff_permission_names(staff_user: User) -> None:
    permissions = get_user_permission_names(staff_user)

    assert "clients:read" in permissions
    assert "clients:delete" not in permissions


async def test_unknown_role_has_no_permissions() -> None:
    assert get_permissions_for_role("inexistente") == ()


async def test_admin_can_list_users(
    client: AsyncClient, admin_user: User, admin_token: str
) -> None:
    response = await client.get(f"{AUTH}/users", headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["email"] == admin_user.email
    assert "administrador" in payload["items"][0]["roles"]


async def test_admin_can_list_roles_and_permissions(
    client: AsyncClient, admin_token: str
) -> None:
    roles = await client.get(f"{AUTH}/roles", headers=_auth(admin_token))
    permissions = await client.get(f"{AUTH}/permissions", headers=_auth(admin_token))

    assert roles.status_code == 200
    assert {role["name"] for role in roles.json()} == {
        "administrador",
        "abogado",
        "asistente",
        "cliente",
    }
    by_name = {role["name"]: role for role in roles.json()}
    assert by_name["administrador"]["permissions"] == sorted(ADMINISTRATOR_PERMISSIONS)
    assert "clients:read" in by_name["abogado"]["permissions"]
    assert by_name["cliente"]["permissions"] == [
        "actions:read_published",
        "calendar:read_published",
        "cases:read_published",
        "client_requests:read",
        "client_requests:respond",
        "dashboard:read",
        "documents:read_published",
        "evidences:download_optimized",
        "evidences:view_published",
        "messages:read",
        "messages:send",
        "notifications:read",
    ]
    assert permissions.status_code == 200
    assert "users:read" in {item["name"] for item in permissions.json()}


async def test_admin_can_create_user_with_roles(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.post(
        f"{AUTH}/users",
        json={
            "email": "nuevo.abogado@example.com",
            "password": "testpassword123",
            "full_name": "Nuevo Abogado",
            "role_names": ["abogado"],
        },
        headers=_auth(admin_token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["roles"] == ["abogado"]
    assert payload["is_active"] is True
    assert "hashed_password" not in payload


async def test_admin_create_user_rejects_duplicated_email(
    client: AsyncClient, admin_user: User, admin_token: str
) -> None:
    response = await client.post(
        f"{AUTH}/users",
        json={
            "email": admin_user.email,
            "password": "testpassword123",
        },
        headers=_auth(admin_token),
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "El correo ya está registrado"


async def test_admin_create_user_rejects_unknown_role(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.post(
        f"{AUTH}/users",
        json={
            "email": "rol.invalido@example.com",
            "password": "testpassword123",
            "role_names": ["rol-inexistente"],
        },
        headers=_auth(admin_token),
    )

    assert response.status_code == 400
    assert "Rol desconocido" in response.json()["error"]["message"]


async def test_admin_can_update_user(
    client: AsyncClient, plain_user: User, admin_token: str
) -> None:
    response = await client.patch(
        f"{AUTH}/users/{plain_user.id}",
        json={"full_name": "Nombre Actualizado", "is_verified": True},
        headers=_auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Nombre Actualizado"


async def test_admin_update_unknown_user_returns_404(
    client: AsyncClient, admin_token: str
) -> None:
    from uuid import uuid4

    response = await client.patch(
        f"{AUTH}/users/{uuid4()}",
        json={"full_name": "No existe"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 404


async def test_admin_can_assign_and_revoke_role(
    client: AsyncClient, plain_user: User, admin_token: str
) -> None:
    assigned = await client.post(
        f"{AUTH}/users/{plain_user.id}/roles",
        json={"role_name": "abogado"},
        headers=_auth(admin_token),
    )
    revoked = await client.delete(
        f"{AUTH}/users/{plain_user.id}/roles/abogado",
        headers=_auth(admin_token),
    )

    assert assigned.status_code == 200
    assert set(assigned.json()["roles"]) == {"cliente", "abogado"}
    assert revoked.status_code == 200
    assert revoked.json()["roles"] == ["cliente"]


async def test_admin_soft_deactivates_user(
    client: AsyncClient, plain_user: User, admin_user: User, admin_token: str
) -> None:
    response = await client.delete(
        f"{AUTH}/users/{plain_user.id}", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert plain_user.deleted_at is not None
    assert plain_user.deleted_by == admin_user.id


async def test_admin_cannot_deactivate_itself(
    client: AsyncClient, admin_user: User, admin_token: str
) -> None:
    response = await client.delete(
        f"{AUTH}/users/{admin_user.id}", headers=_auth(admin_token)
    )

    assert response.status_code == 400
    assert "tu propia cuenta" in response.json()["error"]["message"]


async def test_user_without_permission_is_forbidden(
    client: AsyncClient, plain_user_token: str
) -> None:
    response = await client.get(f"{AUTH}/users", headers=_auth(plain_user_token))

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Permiso requerido: users:read"


async def test_anonymous_access_is_rejected(client: AsyncClient) -> None:
    response = await client.get(f"{AUTH}/users")

    assert response.status_code == 401


async def test_superuser_bypasses_permission_matrix(
    client: AsyncClient, database_session: AsyncSession
) -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.security import create_access_token

    now = datetime.now(UTC)
    root = User(
        id=uuid4(),
        email=f"root-{uuid4()}@example.com",
        full_name="Root",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=True,
        created_at=now,
        updated_at=now,
    )
    database_session.add(root)
    await database_session.flush()

    token = create_access_token(subject=root.id)
    response = await client.get(f"{AUTH}/users", headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_require_permission_builds_dependency() -> None:
    dependency = require_permission("users:read")
    assert callable(dependency)


async def test_audit_logs_endpoint_requires_permission(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{AUTH}/audit-logs", headers=_auth(admin_token))

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


async def test_role_response_serializes_permissions(rbac_catalog: dict[str, Role]) -> None:
    from app.schemas.identity import RoleResponse

    response = RoleResponse.from_role(rbac_catalog["cliente"])

    assert response.name == "cliente"
    assert response.permissions == [
        "actions:read_published",
        "calendar:read_published",
        "cases:read_published",
        "client_requests:read",
        "client_requests:respond",
        "dashboard:read",
        "documents:read_published",
        "evidences:download_optimized",
        "evidences:view_published",
        "messages:read",
        "messages:send",
        "notifications:read",
    ]


@pytest.mark.asyncio
async def test_plain_user_has_no_wide_reads(plain_user: User) -> None:
    permissions = get_user_permission_names(plain_user)

    assert permissions == {
        "actions:read_published",
        "calendar:read_published",
        "cases:read_published",
        "client_requests:read",
        "client_requests:respond",
        "dashboard:read",
        "documents:read_published",
        "evidences:download_optimized",
        "evidences:view_published",
        "messages:read",
        "messages:send",
        "notifications:read",
    }


# --- Security module: single user, directory filters, audit trail ----------


async def test_admin_reads_one_user_with_its_roles_and_permissions(
    client: AsyncClient, admin_user: User, admin_token: str
) -> None:
    response = await client.get(
        f"{AUTH}/users/{admin_user.id}", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(admin_user.id)
    assert payload["email"] == admin_user.email
    assert payload["roles"] == ["administrador"]
    assert "users:read" in payload["permissions"]


async def test_single_user_lookup_misses_with_404(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(f"{AUTH}/users/{uuid4()}", headers=_auth(admin_token))

    assert response.status_code == 404
    # Every 404 is normalised to the same body by the global handler, so the
    # route's own wording never reaches the client.
    assert response.json()["error"]["code"] == "not_found"


async def test_user_directory_filters_by_search_role_and_state(
    client: AsyncClient, admin_user: User, admin_token: str
) -> None:
    headers = _auth(admin_token)
    created: dict[str, str] = {}
    for email, full_name, role in (
        ("ana.torres@example.com", "Ana Torres", "abogado"),
        ("luis.pardo@example.com", "Luis Pardo", "asistente"),
    ):
        response = await client.post(
            f"{AUTH}/users",
            json={
                "email": email,
                "password": "testpassword123",
                "full_name": full_name,
                "role_names": [role],
            },
            headers=headers,
        )
        assert response.status_code == 201
        created[role] = response.json()["id"]

    by_search = await client.get(
        f"{AUTH}/users?search=ana.torres", headers=headers
    )
    assert by_search.status_code == 200
    assert by_search.json()["total"] == 1
    assert [item["email"] for item in by_search.json()["items"]] == [
        "ana.torres@example.com"
    ]

    # The filter is over name as well as address: a directory is searched by
    # how people are known, not by how they log in.
    by_name = await client.get(f"{AUTH}/users?search=Pardo", headers=headers)
    assert [item["full_name"] for item in by_name.json()["items"]] == ["Luis Pardo"]

    by_role = await client.get(f"{AUTH}/users?role=asistente", headers=headers)
    assert by_role.json()["total"] == 1
    assert by_role.json()["items"][0]["roles"] == ["asistente"]

    unknown_role = await client.get(f"{AUTH}/users?role=inexistente", headers=headers)
    assert unknown_role.json()["total"] == 0

    deactivated = await client.delete(
        f"{AUTH}/users/{created['asistente']}", headers=headers
    )
    assert deactivated.status_code == 200

    inactive = await client.get(f"{AUTH}/users?is_active=false", headers=headers)
    assert inactive.json()["total"] == 1
    assert inactive.json()["items"][0]["email"] == "luis.pardo@example.com"

    active = await client.get(f"{AUTH}/users?is_active=true", headers=headers)
    assert active.json()["total"] == 2
    assert admin_user.email in {item["email"] for item in active.json()["items"]}


async def test_directory_reads_an_address_the_input_rule_would_refuse(
    client: AsyncClient,
    admin_token: str,
    database_session: AsyncSession,
) -> None:
    # A row the bootstrap CLI wrote without validating: `@wabogados.local` is a
    # special-use domain, so `EmailStr` refuses it. Serialising every user
    # through `UserResponse` means one such row answered the **whole directory**
    # with a 500 — the same failure the `NIF` document type caused for clients,
    # and for the same reason. The input stays strict; the read must not be.
    legacy = User(
        email="legacy@wabogados.local",
        full_name="Legacy Seed",
        hashed_password=hash_password("testpassword123"),
        is_verified=True,
    )
    database_session.add(legacy)
    await database_session.flush()

    response = await client.get(
        f"{AUTH}/users?search=legacy", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert [item["email"] for item in response.json()["items"]] == [
        "legacy@wabogados.local"
    ]


async def test_audit_trail_reports_who_did_what_and_paginates(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    audit_in_test_transaction: AuditLogMiddleware,
) -> None:
    headers = _auth(admin_token)
    for full_name in ("Primera escritura", "Segunda escritura"):
        response = await client.patch(
            f"{AUTH}/users/{admin_user.id}",
            json={"full_name": full_name},
            headers=headers,
        )
        assert response.status_code == 200

    page = await client.get(f"{AUTH}/audit-logs?limit=1&search=users", headers=headers)

    assert page.status_code == 200
    payload = page.json()
    assert payload["limit"] == 1
    assert payload["skip"] == 0
    assert payload["total"] >= 2
    assert len(payload["items"]) == 1
    entry = payload["items"][0]
    assert entry["entity"] == "users"
    # The reason this field exists: without it the trail names nobody.
    assert entry["user_email"] == admin_user.email

    by_user = await client.get(
        f"{AUTH}/audit-logs?user_id={admin_user.id}", headers=headers
    )
    assert by_user.json()["total"] >= 2

    nobody = await client.get(f"{AUTH}/audit-logs?user_id={uuid4()}", headers=headers)
    assert nobody.json()["total"] == 0

    by_result = await client.get(
        f"{AUTH}/audit-logs?result=success", headers=headers
    )
    assert by_result.json()["total"] >= 2

    no_match = await client.get(f"{AUTH}/audit-logs?search=zzz", headers=headers)
    assert no_match.json()["total"] == 0


async def test_identity_writes_commit_their_transaction(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A write that is only flushed is a write that never happened.

    ``get_session`` closes the request's transaction without committing it, so a
    route that lets the service flush and then answers 201 has written nothing:
    the account is created, announced to the caller, and gone. Reading it back
    inside this test cannot catch that, because the fixture shares one session
    (and one SAVEPOINT) across the request and the assertion, and uncommitted
    rows are perfectly visible there. The assertion is therefore made on the
    session itself: every identity write must commit.
    """
    commits = 0
    original_commit = database_session.commit

    async def counting_commit() -> None:
        nonlocal commits
        commits += 1
        await original_commit()

    monkeypatch.setattr(database_session, "commit", counting_commit)
    headers = _auth(admin_token)

    created = await client.post(
        f"{AUTH}/users",
        json={
            "email": "commit.check@example.com",
            "password": "testpassword123",
            "role_names": ["asistente"],
        },
        headers=headers,
    )
    assert created.status_code == 201
    assert commits == 1

    user_id = created.json()["id"]

    updated = await client.patch(
        f"{AUTH}/users/{user_id}", json={"full_name": "Commit Check"}, headers=headers
    )
    assert updated.status_code == 200
    assert commits == 2

    revoked = await client.delete(f"{AUTH}/users/{user_id}/roles/asistente", headers=headers)
    assert revoked.status_code == 200
    assert commits == 3

    assigned = await client.post(
        f"{AUTH}/users/{user_id}/roles",
        json={"role_name": "abogado"},
        headers=headers,
    )
    assert assigned.status_code == 200
    assert commits == 4

    deleted = await client.delete(f"{AUTH}/users/{user_id}", headers=headers)
    assert deleted.status_code == 200
    assert commits == 5
