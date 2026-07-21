from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pcb_cdso.db.models import AuditEvent, User, UserRole

LOGGER = logging.getLogger("pcb_cdso.bootstrap")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BootstrapConfigError(ValueError):
    pass


@dataclass(frozen=True)
class BootstrapResult:
    created: bool
    user_id: str


def hash_password(password: str) -> str:
    return PasswordHash.recommended().hash(password)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise BootstrapConfigError("BOOTSTRAP_ADMIN_EMAIL must be a valid email address")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 12:
        raise BootstrapConfigError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters")


def bootstrap_admin(
    session_factory: sessionmaker[Session],
    *,
    email: str,
    password: str,
) -> BootstrapResult:
    with session_factory.begin() as session:
        existing = session.scalar(select(User).where(User.role == UserRole.ADMIN).limit(1))
        if existing is not None:
            LOGGER.info("bootstrap administrator already exists", extra={"user_id": existing.id})
            return BootstrapResult(created=False, user_id=existing.id)

        normalized_email = normalize_email(email)
        validate_password(password)
        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        session.flush()
        session.add(
            AuditEvent(
                event_type="admin.bootstrap.created",
                actor_user_id=user.id,
                payload={"email": normalized_email},
            )
        )
        LOGGER.info("bootstrap administrator created", extra={"user_id": user.id})
        return BootstrapResult(created=True, user_id=user.id)


def main() -> int:
    from pcb_cdso.core.config import get_settings
    from pcb_cdso.db.session import build_engine, build_session_factory

    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    settings = get_settings()
    try:
        result = bootstrap_admin(
            build_session_factory(build_engine(settings)),
            email=email,
            password=password,
        )
    except BootstrapConfigError as error:
        LOGGER.error("bootstrap configuration invalid: %s", error)
        return 2
    LOGGER.info("bootstrap complete", extra={"created": result.created, "user_id": result.user_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
