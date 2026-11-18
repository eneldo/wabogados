#!/usr/bin/env python3
"""Seed only a disposable APP_ENVIRONMENT=test installation, never live accounts.

Run inside the isolated API container; output is a temporary JSON credential
bundle for Playwright (redirect with umask 077). Passwords are random and omitted.
"""

import asyncio
import json
import secrets

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.models import Role, User
from app.security import hash_password
from app.services.auth import TokenService


async def main() -> None:
    if get_settings().app_environment != "test":
        raise RuntimeError("Solo se permite sembrar en una instalación test aislada")
    async with SessionFactory() as session:
        if await session.scalar(select(User.id).limit(1)) is not None:
            raise RuntimeError("La base de revisión debe estar vacía de usuarios")
        role = await session.scalar(select(Role).where(Role.name == "administrador"))
        client = await session.scalar(select(Role).where(Role.name == "cliente"))
        assert role is not None and client is not None
        admin = User(email="recovery-admin@example.com", is_verified=True,
                     hashed_password=hash_password(secrets.token_urlsafe(32)), roles=[role])
        target = User(email="recovery-target@example.com", full_name="Cuenta sintética de recuperación",
                      is_verified=True, hashed_password=hash_password(secrets.token_urlsafe(32)),
                      roles=[client])
        unverified = User(email="recovery-unverified@example.com", is_verified=False,
                          hashed_password=hash_password(secrets.token_urlsafe(32)))
        session.add_all([admin, target, unverified])
        await session.flush()
        access, _ = await TokenService(session).issue_session(admin)
        old_access, old_refresh = await TokenService(session).issue_session(target)
        await session.commit()
        print(json.dumps({"access": access, "target_id": str(target.id), "target_email": target.email,
                          "old_access": old_access, "old_refresh": old_refresh}))


if __name__ == "__main__":
    asyncio.run(main())
