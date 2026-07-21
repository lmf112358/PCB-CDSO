"""Auth and session tests (ADR-0002).

Tests AuthService directly against an in-memory SQLite database seeded with
the M0/M1 schema, plus HTTP-level tests via TestClient with an injected
AuthService. SQLite is sufficient here because auth logic is storage-agnostic;
MySQL-specific migration behavior is covered by test_migration_0001/0002.py.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from pcb_cdso.db.base import Base
from pcb_cdso.db.models import AuthSession, AuditEvent, User, UserRole
from pcb_cdso.http.auth import (
    ACCESS_TOKEN_TTL_SECONDS,
    AuthService,
    build_auth_router,
    build_get_actor,
)
from pcb_cdso.http.errors import ApiError
from pcb_cdso.bootstrap import hash_password


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    # sqlite :memory: defaults to one DB per connection; use StaticPool so
    # every session in the test sees the same in-memory schema and rows.
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def auth_service(session_factory: sessionmaker[Session]) -> AuthService:
    return AuthService(session_factory)


def _make_user(
    session_factory: sessionmaker[Session],
    *,
    email: str = "engineer@example.com",
    password: str = "M1-test-password-0000",
    role: UserRole = UserRole.ENGINEER,
    is_active: bool = True,
    locale: str = "zh-CN",
    theme: str = "light",
) -> User:
    with session_factory.begin() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
            locale=locale,
            theme=theme,
        )
        session.add(user)
        session.flush()
        # detach for caller convenience
        session.refresh(user)
        return User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            locale=user.locale,
            theme=user.theme,
        )


# ----- AuthService.login -----


class TestLogin:
    def test_login_returns_session_envelope_with_user(self, auth_service, session_factory):
        _make_user(session_factory)
        envelope, user_id = auth_service.login(
            email="engineer@example.com", password="M1-test-password-0000"
        )
        assert envelope.user.email == "engineer@example.com"
        assert envelope.user.role == UserRole.ENGINEER
        assert envelope.user.is_active is True
        assert envelope.locale == "zh-CN"
        assert envelope.theme == "light"
        assert len(envelope.access_token) >= 16
        assert len(envelope.refresh_token) >= 16
        assert envelope.access_token != envelope.refresh_token
        assert envelope.expires_in == ACCESS_TOKEN_TTL_SECONDS

    def test_login_persists_hashed_tokens_never_raw(self, auth_service, session_factory):
        _make_user(session_factory)
        envelope, _ = auth_service.login(
            email="engineer@example.com", password="M1-test-password-0000"
        )
        with session_factory() as session:
            record = session.scalar(select(AuthSession))
            assert record is not None
            assert record.token_hash != envelope.access_token
            assert record.refresh_token_hash != envelope.refresh_token
            assert record.revoked_at is None
            # 64-char sha256 hex
            assert len(record.token_hash) == 64
            assert len(record.refresh_token_hash) == 64

    def test_login_wrong_password_returns_unauthenticated_without_leak(
        self, auth_service, session_factory
    ):
        _make_user(session_factory)
        with pytest.raises(ApiError) as exc_info:
            auth_service.login(
                email="engineer@example.com", password="wrong-password"
            )
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "UNAUTHENTICATED"
        # message_key must not distinguish missing user from wrong password
        assert exc_info.value.message_key == "auth.login.invalid_credentials"

    def test_login_unknown_user_same_error_as_wrong_password(
        self, auth_service, session_factory
    ):
        _make_user(session_factory)
        with pytest.raises(ApiError) as unknown_exc:
            auth_service.login(email="ghost@example.com", password="anything")
        with pytest.raises(ApiError) as wrong_exc:
            auth_service.login(
                email="engineer@example.com", password="wrong"
            )
        assert unknown_exc.value.code == wrong_exc.value.code
        assert unknown_exc.value.message_key == wrong_exc.value.message_key

    def test_login_email_is_case_insensitive_and_trimmed(self, auth_service, session_factory):
        _make_user(session_factory)
        envelope, _ = auth_service.login(
            email="  Engineer@Example.COM  ", password="M1-test-password-0000"
        )
        assert envelope.user.email == "engineer@example.com"

    def test_login_inactive_user_rejected(self, auth_service, session_factory):
        _make_user(session_factory, is_active=False)
        with pytest.raises(ApiError) as exc:
            auth_service.login(
                email="engineer@example.com", password="M1-test-password-0000"
            )
        assert exc.value.code == "UNAUTHENTICATED"

    def test_login_writes_audit_event(self, auth_service, session_factory):
        _make_user(session_factory)
        auth_service.login(
            email="engineer@example.com", password="M1-test-password-0000"
        )
        with session_factory() as session:
            events = session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "auth.login.succeeded")
            ).all()
            assert len(events) == 1


# ----- AuthService.refresh -----


class TestRefresh:
    def test_refresh_rotates_both_tokens_and_invalidates_old(
        self, auth_service, session_factory
    ):
        _make_user(session_factory)
        envelope, _ = auth_service.login(
            email="engineer@example.com", password="M1-test-password-0000"
        )
        rotated = auth_service.refresh(refresh_token=envelope.refresh_token)
        assert rotated.access_token != envelope.access_token
        assert rotated.refresh_token != envelope.refresh_token

        # Old refresh token must no longer work.
        with pytest.raises(ApiError) as exc:
            auth_service.refresh(refresh_token=envelope.refresh_token)
        assert exc.value.code == "UNAUTHENTICATED"

        # Old access token must no longer resolve.
        with pytest.raises(ApiError) as access_exc:
            auth_service.resolve_actor(access_token=envelope.access_token)
        assert access_exc.value.code == "UNAUTHENTICATED"

    def test_refresh_unknown_token_rejected(self, auth_service):
        with pytest.raises(ApiError) as exc:
            auth_service.refresh(refresh_token="not-a-real-token-but-long-enough-1234567890")
        assert exc.value.code == "UNAUTHENTICATED"


# ----- AuthService.logout + resolve_actor -----


class TestLogoutAndResolve:
    def test_logout_revokes_session_and_becomes_unresolvable(
        self, auth_service, session_factory
    ):
        _make_user(session_factory)
        envelope, _ = auth_service.login(
            email="engineer@example.com", password="M1-test-password-0000"
        )
        # Before logout: resolves OK.
        context, _ = auth_service.resolve_actor(access_token=envelope.access_token)
        assert context.actor_id is not None
        auth_service.logout(access_token=envelope.access_token)
        # After logout: rejected as expired/invalid.
        with pytest.raises(ApiError):
            auth_service.resolve_actor(access_token=envelope.access_token)

    def test_logout_is_idempotent(self, auth_service):
        # Unknown token still returns without raising (no existence leak).
        auth_service.logout(access_token="some-unknown-but-long-token-1234567890")

    def test_resolve_actor_missing_token_raises(self, auth_service):
        with pytest.raises(ApiError) as exc:
            auth_service.resolve_actor(access_token="")
        assert exc.value.code == "UNAUTHENTICATED"
        assert exc.value.message_key == "auth.token.missing"

    def test_resolve_actor_expired_token_rejected(self, auth_service, session_factory):
        user = _make_user(session_factory)
        # Manually craft a session whose expires_at is in the past.
        from pcb_cdso.http.auth import _generate_token_pair, _hash_token, _now

        access_raw, refresh_raw = _generate_token_pair()
        with session_factory.begin() as session:
            session.add(
                AuthSession(
                    user_id=user.id,
                    token_hash=_hash_token(access_raw),
                    refresh_token_hash=_hash_token(refresh_raw),
                    issued_at=_now() - timedelta(hours=2),
                    last_seen_at=_now() - timedelta(hours=2),
                    expires_at=_now() - timedelta(seconds=1),
                )
            )
        with pytest.raises(ApiError) as exc:
            auth_service.resolve_actor(access_token=access_raw)
        assert exc.value.code == "UNAUTHENTICATED"


# ----- deactivate cascades to session revoke (ADR-0002) -----


class TestUserDeactivation:
    def test_deactivating_user_revokes_all_active_sessions(
        self, auth_service, session_factory
    ):
        _make_user(session_factory)
        envelope, _ = auth_service.login(
            email="engineer@example.com", password="M1-test-password-0000"
        )
        # Resolve works pre-deactivation.
        auth_service.resolve_actor(access_token=envelope.access_token)

        # Simulate ADMIN deactivation: is_active=False + revoke all sessions.
        with session_factory.begin() as session:
            db_user = session.scalar(select(User).where(User.email == "engineer@example.com"))
            assert db_user is not None
            db_user.is_active = False
        revoked = auth_service.revoke_all_user_sessions(user_id=envelope.user.id)
        assert revoked == 1

        with pytest.raises(ApiError):
            auth_service.resolve_actor(access_token=envelope.access_token)


# ----- HTTP layer via TestClient with injected AuthService -----


def _client_with_auth(auth_service: AuthService) -> TestClient:
    from pcb_cdso.main import create_app

    return TestClient(
        create_app(
            db_probe=lambda: True,
            redis_probe=lambda: True,
            auth_service=auth_service,
        )
    )


class TestAuthHttp:
    def test_login_endpoint_returns_envelope(self, auth_service, session_factory):
        _make_user(session_factory)
        client = _client_with_auth(auth_service)
        response = client.post(
            "/auth/login",
            json={"email": "engineer@example.com", "password": "M1-test-password-0000"},
            headers={"X-Request-ID": "req-auth-0000000000000001"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["email"] == "engineer@example.com"
        assert body["locale"] == "zh-CN"
        assert body["theme"] == "light"
        assert response.headers["X-Request-ID"] == "req-auth-0000000000000001"

    def test_login_endpoint_wrong_password_returns_401_envelope(
        self, auth_service, session_factory
    ):
        _make_user(session_factory)
        client = _client_with_auth(auth_service)
        response = client.post(
            "/auth/login",
            json={"email": "engineer@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "UNAUTHENTICATED"
        assert body["message_key"] == "auth.login.invalid_credentials"

    def test_me_endpoint_requires_bearer(self, auth_service):
        client = _client_with_auth(auth_service)
        response = client.get("/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"

    def test_me_endpoint_returns_actor_context_after_login(
        self, auth_service, session_factory
    ):
        _make_user(session_factory, role=UserRole.ADMIN, locale="en-US", theme="dark")
        client = _client_with_auth(auth_service)
        login = client.post(
            "/auth/login",
            json={"email": "engineer@example.com", "password": "M1-test-password-0000"},
        )
        token = login.json()["access_token"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        body = me.json()
        assert body["role"] == "ADMIN"
        assert body["locale"] == "en-US"
        assert body["theme"] == "dark"

    def test_logout_then_me_rejected(self, auth_service, session_factory):
        _make_user(session_factory)
        client = _client_with_auth(auth_service)
        login = client.post(
            "/auth/login",
            json={"email": "engineer@example.com", "password": "M1-test-password-0000"},
        )
        token = login.json()["access_token"]
        logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout.status_code == 204
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401
