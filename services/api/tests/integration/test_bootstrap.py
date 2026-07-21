from __future__ import annotations

import logging

import pytest
from pwdlib import PasswordHash
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from pcb_cdso.bootstrap import BootstrapConfigError, bootstrap_admin
from pcb_cdso.db.base import Base
from pcb_cdso.db.models import AuditEvent, User, UserRole


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_bootstrap_creates_one_hashed_admin_and_audit(
    session_factory: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    password = "M0-local-only-password!"
    caplog.set_level(logging.INFO)

    result = bootstrap_admin(
        session_factory,
        email="ADMIN@Example.COM ",
        password=password,
    )

    assert result.created is True
    with session_factory() as session:
        user = session.scalar(select(User))
        assert user is not None
        assert user.email == "admin@example.com"
        assert user.role == UserRole.ADMIN
        assert user.is_active is True
        assert user.password_hash != password
        assert PasswordHash.recommended().verify(password, user.password_hash)
        audit = session.scalar(select(AuditEvent))
        assert audit is not None
        assert audit.event_type == "admin.bootstrap.created"
        assert audit.actor_user_id == user.id
        assert audit.payload == {"email": "admin@example.com"}
    assert password not in caplog.text


def test_bootstrap_is_idempotent_when_an_admin_exists(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = bootstrap_admin(
        session_factory,
        email="admin@example.com",
        password="M0-local-only-password!",
    )

    def hashing_must_not_run(_password: str) -> str:
        raise AssertionError("existing administrator must not re-read/hash the password")

    monkeypatch.setattr("pcb_cdso.bootstrap.hash_password", hashing_must_not_run)
    second = bootstrap_admin(
        session_factory,
        email="different@example.com",
        password="another-local-password!",
    )

    assert first.created is True
    assert second.created is False
    assert second.user_id == first.user_id
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("", "M0-local-only-password!"),
        ("not-an-email", "M0-local-only-password!"),
        ("admin@example.com", "short"),
    ],
)
def test_invalid_bootstrap_config_does_not_write(
    session_factory: sessionmaker[Session], email: str, password: str
) -> None:
    with pytest.raises(BootstrapConfigError):
        bootstrap_admin(session_factory, email=email, password=password)

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 0
