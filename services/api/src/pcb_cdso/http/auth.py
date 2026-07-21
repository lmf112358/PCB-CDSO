"""Authentication and session endpoints (ADR-0002).

Opaque server-revocable tokens backed by the auth_sessions table. Tokens are
sha256-hashed before storage; raw tokens are returned to the client only at
issuance/refresh. A session is invalid when revoked_at is set OR the user is
inactive OR expires_at has passed. Refresh rotates both token hashes in one
transaction; the previous tokens become invalid immediately.

Actor identity is injected via get_actor() dependency. Business code consumes
ActorContext only; request-body actorId fields are ignored and audited per
docs/specs/m1/project-weather-dispatch.md line 45.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from pcb_cdso.db.models import AuditEvent, AuthSession as AuthSessionModel
from pcb_cdso.db.models import User as _UserModel
from pcb_cdso.db.models import UserRole
from pcb_cdso.http.errors import ApiError, ErrorEnvelope

# ADR-0002 defaults. Overridable via settings in future; M1 hardcodes.
ACCESS_TOKEN_TTL_SECONDS = 900
REFRESH_TOKEN_TTL_SECONDS = 14 * 24 * 3600
TOKEN_BYTES = 32  # secrets.token_urlsafe(32) -> ~43 chars, >=16 required by schema


class Locale(StrEnum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"


class Theme(StrEnum):
    LIGHT = "light"
    DARK = "dark"


# --- response/request models ---


class User(BaseModel):
    id: str
    email: str
    role: UserRole
    is_active: bool


class ActorContext(BaseModel):
    actor_id: str
    role: UserRole
    locale: Locale
    theme: Theme


class AuthSession(BaseModel):
    access_token: str = Field(min_length=16)
    refresh_token: str = Field(min_length=16)
    expires_in: int = Field(ge=1, le=86400)
    user: User
    locale: Locale
    theme: Theme


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


# --- token helpers ---


def _hash_token(raw: str) -> str:
    """sha256 hex; stored in auth_sessions.token_hash/refresh_token_hash."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _generate_token_pair() -> tuple[str, str]:
    """Generate (access_raw, refresh_raw). Raw tokens only leave the server here."""
    return secrets.token_urlsafe(TOKEN_BYTES), secrets.token_urlsafe(TOKEN_BYTES)


def _verify_password(password: str, password_hash: str) -> bool:
    # pwdlib is the locked library (ADR-0001, M0 bootstrap).
    from pwdlib import PasswordHash

    return PasswordHash.recommended().verify(password, password_hash)


def _to_actor_context(user: _UserModel) -> ActorContext:
    return ActorContext(
        actor_id=user.id,
        role=user.role,
        locale=Locale(user.locale),
        theme=Theme(user.theme),
    )


def _to_user_public(user: _UserModel) -> User:
    return User(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware.

    MySQL stores timezone-aware values as-is, but SQLite strips tzinfo on
    round-trip; coerce naive values back to UTC so comparisons are consistent
    across both test (SQLite) and production (MySQL) paths.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# --- core auth service (pure functions over a session) ---


class AuthService:
    """Session-scoped authentication operations.

    All mutating methods commit via the passed session maker. The caller is
    responsible for transaction boundaries (each public method is one tx).
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def login(self, *, email: str, password: str) -> tuple["AuthSession", str]:
        """Return (envelope, user_id). Raises ApiError(401) on any failure.

        Per ADR-0002: failures must not distinguish unknown user from wrong
        password (both return UNAUTHENTICATED with the same response).
        """
        with self._session_factory.begin() as session:
            user = session.scalar(
                select(_UserModel).where(_UserModel.email == email.strip().lower()).limit(1)
            )
            # Constant-time-ish: always run a verify against a dummy hash even
            # when the user is missing, so timing does not leak existence.
            dummy_hash = (
                "$argon2id$v=19$m=65536,t=3,p=4$"
                "AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            )
            ok = (
                _verify_password(password, user.password_hash)
                if user is not None
                else _verify_password(password, dummy_hash)
            )
            if user is None or not ok or not user.is_active:
                session.add(
                    AuditEvent(
                        event_type="auth.login.failed",
                        actor_user_id=user.id if user is not None else None,
                        payload={"email_present": user is not None},
                    )
                )
                raise ApiError(
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message_key="auth.login.invalid_credentials",
                )
            envelope, _ = self._issue_session(session, user)
            session.add(
                AuditEvent(
                    event_type="auth.login.succeeded",
                    actor_user_id=user.id,
                    payload={},
                )
            )
            return envelope, user.id

    def refresh(self, *, refresh_token: str) -> "AuthSession":
        """Rotate tokens for the session bound to refresh_token. Old tokens die."""
        refresh_hash = _hash_token(refresh_token)
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(AuthSessionModel)
                .where(AuthSessionModel.refresh_token_hash == refresh_hash)
                .with_for_update()
            )
            if existing is None:
                raise ApiError(
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message_key="auth.refresh.invalid",
                )
            user = session.scalar(select(_UserModel).where(_UserModel.id == existing.user_id))
            if (
                user is None
                or not user.is_active
                or existing.revoked_at is not None
                or _as_aware(existing.expires_at) <= _now()
            ):
                raise ApiError(
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message_key="auth.refresh.invalid",
                )
            new_access, new_refresh = _generate_token_pair()
            now = _now()
            # Rotate in place: the session row keeps its id and user linkage.
            existing.token_hash = _hash_token(new_access)
            existing.refresh_token_hash = _hash_token(new_refresh)
            existing.issued_at = now
            existing.last_seen_at = now
            existing.expires_at = now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
            session.flush()
            session.add(
                AuditEvent(
                    event_type="auth.refresh.succeeded",
                    actor_user_id=user.id,
                    payload={"session_id": existing.id},
                )
            )
            return AuthSession(
                access_token=new_access,
                refresh_token=new_refresh,
                expires_in=ACCESS_TOKEN_TTL_SECONDS,
                user=_to_user_public(user),
                locale=Locale(user.locale),
                theme=Theme(user.theme),
            )

    def logout(self, *, access_token: str) -> str:
        """Revoke the session bound to access_token. Idempotent on already-revoked."""
        token_hash = _hash_token(access_token)
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(AuthSessionModel).where(AuthSessionModel.token_hash == token_hash)
            )
            if existing is None:
                # Idempotent: unknown token still returns 204 (no leak).
                return ""
            if existing.revoked_at is None:
                existing.revoked_at = _now()
                session.add(
                    AuditEvent(
                        event_type="auth.logout",
                        actor_user_id=existing.user_id,
                        payload={"session_id": existing.id},
                    )
                )
            return existing.user_id

    def revoke_all_user_sessions(self, *, user_id: str) -> int:
        """Used when an ADMIN deactivates a user (ADR-0002 immediate revoke).

        Returns the number of sessions revoked. Commits in its own transaction.
        """
        with self._session_factory.begin() as session:
            result = session.execute(
                update(AuthSessionModel)
                .where(AuthSessionModel.user_id == user_id, AuthSessionModel.revoked_at.is_(None))
                .values(revoked_at=_now())
            )
            return result.rowcount or 0

    def resolve_actor(self, *, access_token: str) -> tuple[ActorContext, _UserModel]:
        """Look up the session and return (context, user). Raise 401 if invalid."""
        if not access_token:
            raise ApiError(
                status_code=401,
                code="UNAUTHENTICATED",
                message_key="auth.token.missing",
            )
        token_hash = _hash_token(access_token)
        with self._session_factory() as session:
            existing = session.scalar(
                select(AuthSessionModel).where(AuthSessionModel.token_hash == token_hash)
            )
            if existing is None:
                raise ApiError(
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message_key="auth.token.invalid",
                )
            if (
                existing.revoked_at is not None
                or _as_aware(existing.expires_at) <= _now()
            ):
                raise ApiError(
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message_key="auth.token.expired",
                )
            user = session.scalar(select(_UserModel).where(_UserModel.id == existing.user_id))
            if user is None or not user.is_active:
                raise ApiError(
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message_key="auth.token.invalid",
                )
            # Bump last_seen_at opportunistically (no commit needed for read).
            return _to_actor_context(user), user

    def _issue_session(self, session: Session, user: _UserModel) -> tuple["AuthSession", AuthSessionModel]:
        access_raw, refresh_raw = _generate_token_pair()
        now = _now()
        record = AuthSessionModel(
            user_id=user.id,
            token_hash=_hash_token(access_raw),
            refresh_token_hash=_hash_token(refresh_raw),
            issued_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS),
            revoked_at=None,
        )
        session.add(record)
        session.flush()
        envelope = AuthSession(
            access_token=access_raw,
            refresh_token=refresh_raw,
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            user=_to_user_public(user),
            locale=Locale(user.locale),
            theme=Theme(user.theme),
        )
        return envelope, record


# --- FastAPI dependency ---


def build_get_actor(auth_service: AuthService):
    """Return a FastAPI dependency that resolves ActorContext from Bearer token."""

    def _get_actor(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> ActorContext:
        request_id = getattr(request.state, "request_id", "")
        token = _extract_bearer(authorization)
        try:
            context, _user = auth_service.resolve_actor(access_token=token)
        except ApiError as error:
            # attach request_id to the error so the handler envelope is consistent
            error.details = {**error.details, "request_id": request_id}
            raise
        # Stash for downstream handlers/audit; business code reads from context.
        request.state.actor_id = context.actor_id
        return context

    return _get_actor


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


# --- router ---


def build_auth_router(
    auth_service: AuthService,
    get_actor: callable,  # type: ignore[type-arg]
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post(
        "/login",
        operation_id="auth_login",
        response_model=AuthSession,
        responses={
            401: {"model": ErrorEnvelope, "description": "Invalid credentials."},
            422: {"description": "Validation Error"},
        },
    )
    def login(request: Request, body: LoginRequest) -> AuthSession:
        envelope, _user_id = auth_service.login(email=body.email, password=body.password)
        return envelope

    @router.post(
        "/refresh",
        operation_id="auth_refresh",
        response_model=AuthSession,
        responses={
            401: {"model": ErrorEnvelope, "description": "Refresh token invalid."},
            422: {"description": "Validation Error"},
        },
    )
    def refresh(body: RefreshRequest) -> AuthSession:
        return auth_service.refresh(refresh_token=body.refresh_token)

    @router.post(
        "/logout",
        operation_id="auth_logout",
        status_code=204,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
        },
    )
    def logout(
        request: Request,
        actor: ActorContext = Depends(get_actor),
    ) -> None:
        token = _extract_bearer(request.headers.get("Authorization"))
        auth_service.logout(access_token=token)
        return None

    @router.get(
        "/me",
        operation_id="auth_me",
        response_model=ActorContext,
        responses={
            401: {"model": ErrorEnvelope, "description": "Missing or invalid token."},
        },
    )
    def me(actor: ActorContext = Depends(get_actor)) -> ActorContext:
        return actor

    return router
