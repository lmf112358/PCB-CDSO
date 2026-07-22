"""ConversationService unit tests (M2 skeleton).

Covers the normal COMMITTED path: snapshot lazy-create, draft CAS,
challenge issue + confirm, revision increment, audit record, stage
advancement. WARNING_CONFIRMATION / BLOCKED are out of scope (TODO).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pcb_cdso.db.base import Base
from pcb_cdso.db.models import (
    ConversationAudit,
    ConversationMessage,
    ConversationMessageType,
    ConversationStage,
    Project,
    Template,
    TemplateVersion,
    User,
    UserRole,
)
from pcb_cdso.bootstrap import hash_password
from pcb_cdso.domain.conversation import ConversationService, STAGE_ORDER
from pcb_cdso.http.errors import ApiError


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
def conversation_service(session_factory):
    return ConversationService(session_factory)


@pytest.fixture
def project_owner(session_factory):
    """Seed a user + template + project owned by the user. Return (user_id, project_id)."""
    with session_factory.begin() as session:
        user = User(
            email="engineer@example.com",
            password_hash=hash_password("M1-test-password-0000"),
            role=UserRole.ENGINEER,
            is_active=True,
            locale="zh-CN",
            theme="light",
        )
        session.add(user)
        tpl = Template(slug="hdi", display_name="HDI")
        session.add(tpl)
        session.flush()
        tv = TemplateVersion(
            template_id=tpl.id, version_label="v1.0.0", status="PUBLISHED", payload={}
        )
        session.add(tv)
        session.flush()
        project = Project(
            name="P",
            owner_id=user.id,
            template_version_id=tv.id,
            country_code="CN",
            admin_area="X",
            city="Y",
            timezone="Asia/Shanghai",
            status="ACTIVE",
            input_revision=1,
            ownership_version=1,
        )
        session.add(project)
        session.flush()
        return user.id, project.id


# ----- snapshot -----


class TestSnapshot:
    def test_snapshot_lazy_creates_conversation_with_all_stages_todo(
        self, conversation_service, project_owner
    ):
        user_id, project_id = project_owner
        snap = conversation_service.snapshot(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
        )
        assert snap.conversation_id
        assert snap.input_revision == 1
        assert len(snap.messages) == 0
        # All 8 stages start as 'todo' (stage_state keys reflect stage enum values).
        for stage in STAGE_ORDER:
            assert snap.stage_state[stage.value] == "todo"
        # First unfinished stage is the first in order.
        assert snap.first_unfinished_stage == STAGE_ORDER[0].value

    def test_snapshot_cross_owner_returns_404(self, conversation_service, project_owner):
        _, project_id = project_owner
        with pytest.raises(ApiError) as exc:
            conversation_service.snapshot(
                project_id=project_id,
                actor_id="some-other-user-id",
                actor_role=UserRole.ENGINEER,
            )
        assert exc.value.status_code == 404
        assert exc.value.code == "NOT_FOUND"

    def test_snapshot_unknown_project_returns_404(self, conversation_service, project_owner):
        user_id, _ = project_owner
        with pytest.raises(ApiError) as exc:
            conversation_service.snapshot(
                project_id="nonexistent-project-id",
                actor_id=user_id,
                actor_role=UserRole.ENGINEER,
            )
        assert exc.value.status_code == 404
        # Cross-owner existing id and random unknown id must be indistinguishable.
        assert exc.value.message_key == "projects.not_found"


# ----- draft CAS -----


class TestDraftCas:
    def test_create_draft_returns_version_1(self, conversation_service, project_owner):
        user_id, project_id = project_owner
        result = conversation_service.save_draft(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            scope_key="area:z1:m2",
            expected_draft_version=None,
            content={"value": 100, "unit": "m^2"},
        )
        assert result.draft_version == 1
        assert result.scope_key == "area:z1:m2"

    def test_update_draft_with_correct_version_increments(
        self, conversation_service, project_owner
    ):
        user_id, project_id = project_owner
        first = conversation_service.save_draft(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            scope_key="s1",
            expected_draft_version=None,
            content={"v": 1},
        )
        second = conversation_service.save_draft(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            scope_key="s1",
            expected_draft_version=first.draft_version,
            content={"v": 2},
        )
        assert second.draft_version == first.draft_version + 1
        assert second.content == {"v": 2}

    def test_update_draft_with_stale_version_returns_409(
        self, conversation_service, project_owner
    ):
        user_id, project_id = project_owner
        conversation_service.save_draft(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            scope_key="s1",
            expected_draft_version=None,
            content={"v": 1},
        )
        latest = conversation_service.save_draft(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            scope_key="s1",
            expected_draft_version=1,
            content={"v": 2},
        )
        # Now try with stale version 1 (latest is 2).
        with pytest.raises(ApiError) as exc:
            conversation_service.save_draft(
                project_id=project_id,
                actor_id=user_id,
                actor_role=UserRole.ENGINEER,
                scope_key="s1",
                expected_draft_version=1,
                content={"v": 3},
            )
        assert exc.value.status_code == 409
        assert exc.value.code == "DRAFT_CONFLICT"

    def test_create_existing_draft_with_none_version_returns_409(
        self, conversation_service, project_owner
    ):
        user_id, project_id = project_owner
        conversation_service.save_draft(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            scope_key="s1",
            expected_draft_version=None,
            content={"v": 1},
        )
        with pytest.raises(ApiError) as exc:
            conversation_service.save_draft(
                project_id=project_id,
                actor_id=user_id,
                actor_role=UserRole.ENGINEER,
                scope_key="s1",
                expected_draft_version=None,
                content={"v": 2},
            )
        assert exc.value.code == "DRAFT_CONFLICT"


# ----- challenge + confirm -----


class TestChallengeConfirm:
    def test_confirm_commits_and_advances_revision(
        self, conversation_service, project_owner, session_factory
    ):
        user_id, project_id = project_owner
        challenge = conversation_service.issue_challenge(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            question_key="project_template.first",
            canonical_payload={"productType": "HDI"},
        )
        result = conversation_service.confirm(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            challenge_id=challenge.challenge_id,
            impact_token=challenge.impact_token,
            expected_input_revision=challenge.expected_input_revision,
            canonical_payload={"productType": "HDI"},
            stage=ConversationStage.PROJECT_TEMPLATE,
            question_key="project_template.first",
            field_path="project.templateVersionId",
            canonical_value="hdi-v1",
            unit=None,
            rule_version="m2.skeleton.v1",
            request_id="req-test-1234567890abcdef",
        )
        assert result.presentation_state == "COMMITTED"
        assert result.new_input_revision == 2
        assert result.confirmation_message_id

        # Snapshot now reflects the new revision, COMMITTED card, and stage done.
        snap = conversation_service.snapshot(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
        )
        assert snap.input_revision == 2
        assert snap.stage_state["PROJECT_TEMPLATE"] == "done"
        # First unfinished advanced to next stage.
        assert snap.first_unfinished_stage == STAGE_ORDER[1].value
        # One COMMITTED confirmation card in the timeline.
        committed = [m for m in snap.messages if m.payload.get("presentationState") == "COMMITTED"]
        assert len(committed) == 1
        assert committed[0].message_type == ConversationMessageType.CONFIRMATION_CARD.value

        # Audit row written.
        with session_factory() as session:
            audits = session.scalars(select(ConversationAudit)).all()
            assert len(audits) == 1
            audit = audits[0]
            assert audit.field_path == "project.templateVersionId"
            assert audit.revision_before == 1
            assert audit.revision_after == 2
            assert audit.source == "USER_INPUT"

    def test_confirm_consumes_impact_token_exactly_once(
        self, conversation_service, project_owner
    ):
        user_id, project_id = project_owner
        challenge = conversation_service.issue_challenge(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            question_key="q1",
            canonical_payload={"x": 1},
        )
        # First confirm consumes the token.
        conversation_service.confirm(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            challenge_id=challenge.challenge_id,
            impact_token=challenge.impact_token,
            expected_input_revision=challenge.expected_input_revision,
            canonical_payload={"x": 1},
            stage=ConversationStage.PROJECT_TEMPLATE,
            question_key="q1",
            field_path="f1",
            canonical_value=1,
            unit=None,
            rule_version="v1",
            request_id="req-test-aaaaaaaaaaaaaaaa",
        )
        # Second confirm with the same token must be rejected as consumed.
        with pytest.raises(ApiError) as exc:
            conversation_service.confirm(
                project_id=project_id,
                actor_id=user_id,
                actor_role=UserRole.ENGINEER,
                challenge_id=challenge.challenge_id,
                impact_token=challenge.impact_token,
                expected_input_revision=challenge.expected_input_revision,
                canonical_payload={"x": 1},
                stage=ConversationStage.PROJECT_TEMPLATE,
                question_key="q1",
                field_path="f1",
                canonical_value=1,
                unit=None,
                rule_version="v1",
                request_id="req-test-bbbbbbbbbbbbbbbb",
            )
        assert exc.value.code == "IDEMPOTENCY_CONFLICT"

    def test_confirm_with_wrong_token_returns_401(self, conversation_service, project_owner):
        user_id, project_id = project_owner
        challenge = conversation_service.issue_challenge(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            question_key="q1",
            canonical_payload={"x": 1},
        )
        with pytest.raises(ApiError) as exc:
            conversation_service.confirm(
                project_id=project_id,
                actor_id=user_id,
                actor_role=UserRole.ENGINEER,
                challenge_id=challenge.challenge_id,
                impact_token="wrong-token-but-long-enough-1234",
                expected_input_revision=challenge.expected_input_revision,
                canonical_payload={"x": 1},
                stage=ConversationStage.PROJECT_TEMPLATE,
                question_key="q1",
                field_path="f1",
                canonical_value=1,
                unit=None,
                rule_version="v1",
                request_id="req-test-cccccccccccccccc",
            )
        assert exc.value.status_code == 401
        assert exc.value.code == "UNAUTHENTICATED"

    def test_confirm_with_stale_revision_returns_revision_conflict(
        self, conversation_service, project_owner
    ):
        """Revision conflict consumes token but writes nothing."""
        user_id, project_id = project_owner
        challenge = conversation_service.issue_challenge(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            question_key="q1",
            canonical_payload={"x": 1},
        )
        # Pass a stale expected_input_revision (current is 1, claim 99).
        result = conversation_service.confirm(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
            challenge_id=challenge.challenge_id,
            impact_token=challenge.impact_token,
            expected_input_revision=99,
            canonical_payload={"x": 1},
            stage=ConversationStage.PROJECT_TEMPLATE,
            question_key="q1",
            field_path="f1",
            canonical_value=1,
            unit=None,
            rule_version="v1",
            request_id="req-test-dddddddddddddddd",
        )
        assert result.presentation_state == "REVISION_CONFLICT"
        assert result.new_input_revision is None
        assert result.confirmation_message_id == ""
        # Token consumed, but no business value written.
        snap = conversation_service.snapshot(
            project_id=project_id,
            actor_id=user_id,
            actor_role=UserRole.ENGINEER,
        )
        assert snap.input_revision == 1  # unchanged
        assert len(snap.messages) == 0
