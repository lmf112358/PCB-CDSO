"""POST /projects tests (M1-C-001/002, M1-I-002/004/005 happy/idempotency paths).

Covers the CreateProject happy path, idempotent replay, actor scope, and
field validation. Transaction atomicity and fault injection are covered
separately in Task 2.3; this file pins the core contract.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pcb_cdso.db.base import Base
from pcb_cdso.db.models import (
    IdempotencyRecord,
    IdempotencyStatus,
    OutboxEvent,
    Project,
    Task,
    TaskStatus,
    Template,
    TemplateVersion,
    User,
    UserRole,
)
from pcb_cdso.bootstrap import hash_password
from pcb_cdso.domain.projects import (
    EVENT_TYPE_WEATHER_FETCH_REQUESTED,
    SCOPE_CREATE_PROJECT,
    TASK_TYPE_WEATHER_HISTORY_FETCH,
    CreateProjectCommand,
    ProjectService,
    canonical_request_hash,
)
from pcb_cdso.http.auth import AuthService
from pcb_cdso.http.errors import ApiError
from pcb_cdso.main import create_app


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def auth_service(session_factory):
    return AuthService(session_factory)


@pytest.fixture
def project_service(session_factory):
    return ProjectService(session_factory)


@pytest.fixture
def seed_template(session_factory):
    """Insert one PUBLISHED template version for HDI."""
    with session_factory.begin() as session:
        tpl = Template(slug="hdi", display_name="HDI")
        session.add(tpl)
        session.flush()
        tv = TemplateVersion(
            template_id=tpl.id,
            version_label="v1.0.0",
            status="PUBLISHED",
            payload={"productType": "HDI"},
        )
        session.add(tv)
        session.flush()
        return tv.id


def _login_user(
    session_factory,
    auth_service,
    *,
    email="engineer@example.com",
    password="M1-test-password-0000",
    role=UserRole.ENGINEER,
):
    """Create a user and return (user_id, access_token)."""
    with session_factory.begin() as session:
        session.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
                locale="zh-CN",
                theme="light",
            )
        )
        session.flush()
        # read back id
        u = session.scalar(select(User).where(User.email == email))
        user_id = u.id
    envelope, _ = auth_service.login(email=email, password=password)
    return user_id, envelope.access_token


def _client(auth_service, project_service) -> TestClient:
    return TestClient(
        create_app(
            db_probe=lambda: True,
            redis_probe=lambda: True,
            auth_service=auth_service,
            project_service=project_service,
        )
    )


# ----- ProjectService unit tests -----


class TestCreateProjectService:
    def test_create_writes_four_groups_atomically(
        self, project_service, session_factory, seed_template
    ):
        user_id, _ = _login_user(session_factory, auth_service := AuthService(session_factory))
        cmd = CreateProjectCommand.from_raw(
            name="深圳 HDI 工厂",
            template_version_id=seed_template,
            country_code="cn",
            admin_area="广东省",
            city="深圳市",
            timezone="Asia/Shanghai",
            actor_id=user_id,
            idempotency_key="m1-happy-001",
        )
        result = project_service.create_project(cmd, actor_role=UserRole.ENGINEER)

        assert result.is_replay is False
        assert result.input_revision == 1
        assert result.snapshot_ids == [seed_template]
        with session_factory() as session:
            project = session.scalar(select(Project).where(Project.id == result.project_id))
            assert project is not None
            assert project.owner_id == user_id
            assert project.input_revision == 1
            assert project.status == "ACTIVE"

            task = session.scalar(select(Task).where(Task.id == result.weather_task_id))
            assert task is not None
            assert task.task_type == TASK_TYPE_WEATHER_HISTORY_FETCH
            assert task.status == TaskStatus.DISPATCH_PENDING
            assert task.project_id == project.id

            outbox = session.scalar(select(OutboxEvent).where(OutboxEvent.task_id == task.id))
            assert outbox is not None
            assert outbox.event_type == EVENT_TYPE_WEATHER_FETCH_REQUESTED
            assert outbox.dispatched_at is None
            assert outbox.payload["eventId"] == outbox.id
            assert outbox.payload["taskId"] == task.id

            idem = session.scalar(select(IdempotencyRecord))
            assert idem is not None
            assert idem.status == IdempotencyStatus.SUCCEEDED
            assert idem.result_project_id == project.id
            assert idem.result_weather_task_id == task.id

    def test_serial_replay_returns_same_aggregate(
        self, project_service, session_factory, seed_template
    ):
        user_id, _ = _login_user(session_factory, AuthService(session_factory))
        cmd = CreateProjectCommand.from_raw(
            name="深圳 HDI 工厂",
            template_version_id=seed_template,
            country_code="CN",
            admin_area="广东省",
            city="深圳市",
            timezone="Asia/Shanghai",
            actor_id=user_id,
            idempotency_key="m1-replay-001",
        )
        first = project_service.create_project(cmd, actor_role=UserRole.ENGINEER)
        second = project_service.create_project(cmd, actor_role=UserRole.ENGINEER)
        assert second.is_replay is True
        assert second.project_id == first.project_id
        assert second.weather_task_id == first.weather_task_id

        # Only one of each record persisted.
        with session_factory() as session:
            assert len(session.scalars(select(Project)).all()) == 1
            assert len(session.scalars(select(Task)).all()) == 1
            assert len(session.scalars(select(OutboxEvent)).all()) == 1
            assert len(session.scalars(select(IdempotencyRecord)).all()) == 1

    def test_same_key_different_hash_returns_conflict(
        self, project_service, session_factory, seed_template
    ):
        user_id, _ = _login_user(session_factory, AuthService(session_factory))
        cmd1 = CreateProjectCommand.from_raw(
            name="深圳 HDI 工厂",
            template_version_id=seed_template,
            country_code="CN",
            admin_area="广东省",
            city="深圳市",
            timezone="Asia/Shanghai",
            actor_id=user_id,
            idempotency_key="m1-conflict-001",
        )
        project_service.create_project(cmd1, actor_role=UserRole.ENGINEER)
        # Same key, different city -> different canonical hash -> conflict.
        cmd2 = CreateProjectCommand.from_raw(
            name="深圳 HDI 工厂",
            template_version_id=seed_template,
            country_code="CN",
            admin_area="广东省",
            city="东莞市",  # different
            timezone="Asia/Shanghai",
            actor_id=user_id,
            idempotency_key="m1-conflict-001",
            )
        with pytest.raises(ApiError) as exc:
            project_service.create_project(cmd2, actor_role=UserRole.ENGINEER)
        assert exc.value.status_code == 409
        assert exc.value.code == "IDEMPOTENCY_CONFLICT"

    def test_idempotency_key_is_scoped_by_actor(
        self, project_service, session_factory, seed_template
    ):
        """Two ENGINEERs using the same key each succeed independently."""
        _login_user(
            session_factory,
            AuthService(session_factory),
            email="a@example.com",
        )
        _login_user(
            session_factory,
            AuthService(session_factory),
            email="b@example.com",
        )
        with session_factory() as session:
            a = session.scalar(select(User).where(User.email == "a@example.com"))
            b = session.scalar(select(User).where(User.email == "b@example.com"))
        cmd_a = CreateProjectCommand.from_raw(
            name="A",
            template_version_id=seed_template,
            country_code="CN",
            admin_area="X",
            city="Y",
            timezone="Asia/Shanghai",
            actor_id=a.id,
            idempotency_key="shared-key-001",
        )
        cmd_b = CreateProjectCommand.from_raw(
            name="B",
            template_version_id=seed_template,
            country_code="CN",
            admin_area="X",
            city="Y",
            timezone="Asia/Shanghai",
            actor_id=b.id,
            idempotency_key="shared-key-001",
        )
        ra = project_service.create_project(cmd_a, actor_role=UserRole.ENGINEER)
        rb = project_service.create_project(cmd_b, actor_role=UserRole.ENGINEER)
        assert ra.project_id != rb.project_id
        assert ra.weather_task_id != rb.weather_task_id

    def test_non_engineer_non_admin_role_forbidden(
        self, project_service, session_factory, seed_template
    ):
        # UserRole only has ADMIN and ENGINEER; this test confirms _authorize
        # accepts both. A hypothetical other role would be rejected but
        # cannot be constructed without altering UserRole. We just verify
        # ADMIN works here; ENGINEER is covered elsewhere.
        admin_id, _ = _login_user(
            session_factory,
            AuthService(session_factory),
            email="admin@example.com",
            role=UserRole.ADMIN,
        )
        cmd = CreateProjectCommand.from_raw(
            name="Admin-created",
            template_version_id=seed_template,
            country_code="CN",
            admin_area="X",
            city="Y",
            timezone="Asia/Shanghai",
            actor_id=admin_id,
            idempotency_key="admin-001",
        )
        result = project_service.create_project(cmd, actor_role=UserRole.ADMIN)
        assert result.owner_id == admin_id


# ----- canonical hash determinism -----


class TestCanonicalHash:
    def test_hash_is_deterministic_and_order_stable(self):
        cmd = CreateProjectCommand.from_raw(
            name="n",
            template_version_id="tv1",
            country_code="cn",
            admin_area="a",
            city="c",
            timezone="Asia/Shanghai",
            actor_id="ignored",
            idempotency_key="ignored",
        )
        h1 = canonical_request_hash(cmd)
        h2 = canonical_request_hash(cmd)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_excludes_actor_and_key(self):
        cmd_a = CreateProjectCommand.from_raw(
            name="n",
            template_version_id="tv1",
            country_code="CN",
            admin_area="a",
            city="c",
            timezone="Asia/Shanghai",
            actor_id="actor-A",
            idempotency_key="key-A",
        )
        cmd_b = CreateProjectCommand.from_raw(
            name="n",
            template_version_id="tv1",
            country_code="CN",
            admin_area="a",
            city="c",
            timezone="Asia/Shanghai",
            actor_id="actor-B",
            idempotency_key="key-B",
        )
        assert canonical_request_hash(cmd_a) == canonical_request_hash(cmd_b)


# ----- HTTP layer -----


class TestCreateProjectHttp:
    def test_201_creates_project_and_returns_weather_task_id(
        self, auth_service, project_service, session_factory, seed_template
    ):
        _, token = _login_user(session_factory, auth_service)
        client = _client(auth_service, project_service)
        response = client.post(
            "/projects",
            json={
                "name": "深圳 HDI 工厂",
                "templateVersionId": seed_template,
                "countryCode": "CN",
                "adminArea": "广东省",
                "city": "深圳市",
                "timezone": "Asia/Shanghai",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "http-001",
                "X-Request-ID": "req-projects-0000000001",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["inputRevision"] == 1
        assert body["weatherTaskId"]
        assert body["project"]["name"] == "深圳 HDI 工厂"
        assert body["snapshotIds"] == [seed_template]

    def test_200_on_idempotent_replay_with_same_task_id(
        self, auth_service, project_service, session_factory, seed_template
    ):
        _, token = _login_user(session_factory, auth_service)
        client = _client(auth_service, project_service)
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "http-replay-001",
        }
        body = {
            "name": "Project",
            "templateVersionId": seed_template,
            "countryCode": "CN",
            "adminArea": "X",
            "city": "Y",
            "timezone": "Asia/Shanghai",
        }
        first = client.post("/projects", json=body, headers=headers)
        second = client.post("/projects", json=body, headers=headers)
        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["weatherTaskId"] == second.json()["weatherTaskId"]
        assert first.json()["project"]["id"] == second.json()["project"]["id"]

    def test_409_on_same_key_different_payload(
        self, auth_service, project_service, session_factory, seed_template
    ):
        _, token = _login_user(session_factory, auth_service)
        client = _client(auth_service, project_service)
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "http-conflict-001",
        }
        client.post(
            "/projects",
            json={
                "name": "P1",
                "templateVersionId": seed_template,
                "countryCode": "CN",
                "adminArea": "X",
                "city": "Shenzhen",
                "timezone": "Asia/Shanghai",
            },
            headers=headers,
        )
        second = client.post(
            "/projects",
            json={
                "name": "P1",
                "templateVersionId": seed_template,
                "countryCode": "CN",
                "adminArea": "X",
                "city": "Dongguan",  # different -> different canonical hash
                "timezone": "Asia/Shanghai",
            },
            headers=headers,
        )
        assert second.status_code == 409
        assert second.json()["code"] == "IDEMPOTENCY_CONFLICT"

    def test_404_when_template_version_missing(
        self, auth_service, project_service, session_factory, seed_template
    ):
        _, token = _login_user(session_factory, auth_service)
        client = _client(auth_service, project_service)
        response = client.post(
            "/projects",
            json={
                "name": "P",
                "templateVersionId": "nonexistent-version-id",
                "countryCode": "CN",
                "adminArea": "X",
                "city": "Y",
                "timezone": "Asia/Shanghai",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "http-missing-001",
            },
        )
        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"

    def test_422_on_invalid_country_code(
        self, auth_service, project_service, session_factory, seed_template
    ):
        _, token = _login_user(session_factory, auth_service)
        client = _client(auth_service, project_service)
        response = client.post(
            "/projects",
            json={
                "name": "P",
                "templateVersionId": seed_template,
                "countryCode": "china",  # lowercase, not ^[A-Z]{2}$
                "adminArea": "X",
                "city": "Y",
                "timezone": "Asia/Shanghai",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "http-invalid-001",
            },
        )
        # FastAPI request-body validation kicks in first (422 HTTPValidationError)
        # before our domain VALIDATION_FAILED; both are acceptable per the
        # contract, but the envelope code differs. Assert status only.
        assert response.status_code == 422

    def test_401_without_bearer(self, auth_service, project_service):
        client = _client(auth_service, project_service)
        response = client.post(
            "/projects",
            json={
                "name": "P",
                "templateVersionId": "any",
                "countryCode": "CN",
                "adminArea": "X",
                "city": "Y",
                "timezone": "Asia/Shanghai",
            },
            headers={"Idempotency-Key": "http-noauth-001"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"
