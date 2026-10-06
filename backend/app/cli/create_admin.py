"""Create or promote the bootstrap administrator.

Credentials are read from ADMIN_EMAIL / ADMIN_PASSWORD environment variables so
no secret is ever stored in the repository.

Usage:
    python -m app.cli.create_admin
"""

import asyncio
import sys
from collections.abc import Callable

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.models import Role, User, UserRole
from app.security import hash_password

EMAIL = TypeAdapter(EmailStr)


async def create_admin(
    session_factory: Callable[[], AsyncSession] | None = None,
) -> int:
    settings = get_settings()
    email = settings.admin_email
    password = settings.admin_password

    if not email or not password:
        print("[ERROR] Define ADMIN_EMAIL y ADMIN_PASSWORD en el entorno.")
        return 2

    # The CLI writes the row directly, so nothing else would apply the rule the
    # API applies on `POST /users`. Without this, a special-use domain such as
    # `admin@wabogados.local` is created happily and then refuses to be read back
    # by every schema that validates the address on the way out.
    try:
        email = EMAIL.validate_python(email)
    except ValidationError:
        print(f"[ERROR] ADMIN_EMAIL no es una dirección válida: {email}")
        return 2

    factory = session_factory or SessionFactory
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                full_name="Administrador WABOGADOS",
                hashed_password=hash_password(password),
                is_superuser=True,
                is_verified=True,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            action = "created"
        else:
            user.hashed_password = hash_password(password)
            user.is_superuser = True
            user.is_verified = True
            user.is_active = True
            action = "updated"

        role_result = await session.execute(
            select(Role).where(Role.name == "administrador")
        )
        role = role_result.scalar_one_or_none()
        if role is None:
            print(
                "[ERROR] El rol 'administrador' no existe. Ejecuta las migraciones "
                "antes de crear el administrador."
            )
            return 3

        # Check the association with an explicit query: touching `user.roles`
        # would trigger a lazy load outside the async greenlet context.
        assigned = await session.scalar(
            select(UserRole.role_id).where(
                UserRole.user_id == user.id, UserRole.role_id == role.id
            )
        )
        if assigned is None:
            await session.execute(
                insert(UserRole).values(user_id=user.id, role_id=role.id)
            )

        await session.commit()

    print(f"[OK] Administrador {action}: {email}")
    return 0


def main() -> int:
    return asyncio.run(create_admin())


if __name__ == "__main__":
    sys.exit(main())
