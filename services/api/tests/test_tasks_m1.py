"""GET /tasks and GET /tasks/{id} tests.

Covers M1-I-009 anti-enumeration semantics (cross-owner existing id and
random unknown id return indistinguishable 404; ENGINEER list is filtered;
ADMIN sees all) plus the M1-P-001 visibility precondition (a freshly created
project's task is immediately queryable).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pcb_cdso.db.base import Base
from pcb_cdso.db.models import Template, TemplateVersion, User, UserRole
from pcb_cdso.bootstrap import hash_password
from pcb_cdso.domain.projects import CreateProjectCommand, ProjectService
from pcb_cdso.http.auth import AuthService
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
    with session_factory.begin() as session:
        tpl = Template(slug="hdi", display_name="HDI")
        session.add(tpl)
        session.flush()
        tv = TemplateVersion(
            template_id=tpl.id, version_label="v1.0.0", status="PUBLISHED", payload={}
        )
        session.add(tv)
        session.flush()
        return tv.id


def _add_user(session_factory, *, email, role=UserRole.ENGINEER):
    with session_factory.begin() as session:
        session.add(
            User(
                email=email,
                password_hash=hash_password("M1-test-password-0000"),
                role=role,
                is_active=True,
                locale="zh-CN",
                theme="light",
            )
        )
        session.flush()
        return session.scalar(select(User).where(User.email == email)).id


def _login_token(auth_service, email):
    envelope, _ = auth_service.login(email=email, password="M1-test-password-0000")
    return envelope.access_token


def _client(auth_service, project_service, session_factory):
    return TestClient(
        create_app(
            db_probe=lambda: True,
            redis_probe=lambda: True,
            auth_service=auth_service,
            project_service=project_service,
            tasks_session_factory=session_factory,
        )
    )


def _create_project(project_service, session_factory, seed_template, owner_id, key):
    cmd = CreateProjectCommand.from_raw(
        name="P",
        template_version_id=seed_template,
        country_code="CN",
        admin_area="X",
        city="Y",
        timezone="Asia/Shanghai",
        actor_id=owner_id,
        idempotency_key=key,
    )
    return project_service.create_project(cmd, actor_role=UserRole.ENGINEER)


class TestTaskList:
    def test_engineer_sees_only_own_tasks(
        self, auth_service, project_service, session_factory, seed_template
    ):
        a_id = _add_user(session_factory, email="a@example.com")
        b_id = _add_user(session_factory, email="b@example.com")
        _create_project(project_service, session_factory, seed_template, a_id, "ka")
        _create_project(project_service, session_factory, seed_template, b_id, "kb")
        client = _client(auth_service, project_service, session_factory)
        token_a = _login_token(auth_service, "a@example.com")
        token_b = _login_token(auth_service, "b@example.com")
        ra = client.get("/tasks", headers={"Authorization": f"Bearer {token_a}"})
        rb = client.get("/tasks", headers={"Authorization": f"Bearer {token_b}"})
        assert ra.status_code == 200
        assert rb.status_code == 200
        assert len(ra.json()["items"]) == 1
        assert len(rb.json()["items"]) == 1
        assert ra.json()["items"][0]["task_id"] != rb.json()["items"][0]["task_id"]

    def test_admin_sees_all_tasks(
        self, auth_service, project_service, session_factory, seed_template
    ):
        _add_user(session_factory, email="admin@example.com", role=UserRole.ADMIN)
        a_id = _add_user(session_factory, email="a@example.com")
        b_id = _add_user(session_factory, email="b@example.com")
        _create_project(project_service, session_factory, seed_template, a_id, "ka")
        _create_project(project_service, session_factory, seed_template, b_id, "kb")
        client = _client(auth_service, project_service, session_factory)
        token = _login_token(auth_service, "admin@example.com")
        r = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()["items"]) == 2

    def test_project_filter_returns_only_that_project_tasks(
        self, auth_service, project_service, session_factory, seed_template
    ):
        owner = _add_user(session_factory, email="a@example.com")
        result1 = _create_project(project_service, session_factory, seed_template, owner, "k1")
        _create_project(project_service, session_factory, seed_template, owner, "k2")
        client = _client(auth_service, project_service, session_factory)
        token = _login_token(auth_service, "a@example.com")
        r = client.get(
            f"/tasks?projectId={result1.project_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1
        assert r.json()["items"][0]["task_id"] == result1.weather_task_id

    def test_cross_owner_project_filter_returns_empty(
        self, auth_service, project_service, session_factory, seed_template
    ):
        a_id = _add_user(session_factory, email="a@example.com")
        b_id = _add_user(session_factory, email="b@example.com")
        result_a = _create_project(project_service, session_factory, seed_template, a_id, "ka")
        client = _client(auth_service, project_service, session_factory)
        token_b = _login_token(auth_service, "b@example.com")
        # B queries A's project: anti-enumeration returns empty list (200).
        r = client.get(
            f"/tasks?projectId={result_a.project_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r.status_code == 200
        assert r.json()["items"] == []


class TestTaskGet:
    def test_owner_can_get_own_task(self, auth_service, project_service, session_factory, seed_template):
        owner = _add_user(session_factory, email="a@example.com")
        result = _create_project(project_service, session_factory, seed_template, owner, "k")
        client = _client(auth_service, project_service, session_factory)
        token = _login_token(auth_service, "a@example.com")
        r = client.get(
            f"/tasks/{result.weather_task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["task_id"] == result.weather_task_id
        assert r.json()["status"] == "DISPATCH_PENDING"

    def test_cross_owner_existing_id_indistinguishable_from_unknown(
        self, auth_service, project_service, session_factory, seed_template
    ):
        a_id = _add_user(session_factory, email="a@example.com")
        b_id = _add_user(session_factory, email="b@example.com")
        result_a = _create_project(project_service, session_factory, seed_template, a_id, "ka")
        client = _client(auth_service, project_service, session_factory)
        token_b = _login_token(auth_service, "b@example.com")
        r_cross = client.get(
            f"/tasks/{result_a.weather_task_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        r_unknown = client.get(
            "/tasks/nonexistent-random-id-xyz",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        # Both must be 404 with identical envelope shape and message_key.
        assert r_cross.status_code == 404
        assert r_unknown.status_code == 404
        assert r_cross.json()["code"] == r_unknown.json()["code"] == "NOT_FOUND"
        assert r_cross.json()["message_key"] == r_unknown.json()["message_key"]

    def test_admin_can_get_any_task(
        self, auth_service, project_service, session_factory, seed_template
    ):
        _add_user(session_factory, email="admin@example.com", role=UserRole.ADMIN)
        owner = _add_user(session_factory, email="a@example.com")
        result = _create_project(project_service, session_factory, seed_template, owner, "k")
        client = _client(auth_service, project_service, session_factory)
        token = _login_token(auth_service, "admin@example.com")
        r = client.get(
            f"/tasks/{result.weather_task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200


class TestTaskVisibilityAfterCreate:
    def test_freshly_created_task_immediately_queryable(
        self, auth_service, project_service, session_factory, seed_template
    ):
        """M1-P-001 precondition: task is visible immediately after create."""
        owner = _add_user(session_factory, email="a@example.com")
        result = _create_project(project_service, session_factory, seed_template, owner, "k")
        client = _client(auth_service, project_service, session_factory)
        token = _login_token(auth_service, "a@example.com")
        r = client.get(
            f"/tasks/{result.weather_task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["task_id"] == result.weather_task_id
