"""Add M2 conversation workspace tables.

Revision ID: 0003_m2_conversation
Revises: 0002_m1_project_weather_dispatch
Create Date: 2026-07-22

Implements docs/specs/m2/expert-conversation-workspace.md persistence:
- conversation_messages: the four messageType records (AGENT_PROMPT,
  USER_DRAFT, CONFIRMATION_CARD, TOOL_CARD) with stable ids and a
  server-issued sort cursor for deterministic replay.
- conversation_drafts: USER_DRAFT content saved with CAS draftVersion
  per (projectId, scope key); 409 DRAFT_CONFLICT on stale version.
- confirmation_challenges: one-time impactToken + warningChallengeId
  + warningConfirmationToken lifecycle per M2 spec section '唯一业务
  写入路径'.
- conversation_audits: immutable per-COMMITTED audit (actor, field
  path, old/new canonical value, unit, rule version, source, warning
  reasons, before/after revision, request id). No tokens/credentials.

The 8-stage state lives on a per-project cursor column rather than a
separate table; see conversations.project_stage / stage_status JSON.

Constraints are named (uq_*/ck_*/fk_*/ix_*) per governance convention.
Enum widening in later milestones goes through a new migration, never
by editing this file.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_m2_conversation"
down_revision: str | None = "0002_m1_project_weather_dispatch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- conversations: per-project conversation state ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("input_revision", sa.Integer(), nullable=False, server_default="1"),
        # JSON holding the 8-stage completion state; shape documented in
        # ConversationService.stage_state. Kept as JSON so adding stage
        # metadata in later milestones is non-breaking.
        sa.Column("stage_state", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE", name="fk_conversations_project"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_conversations_project"),
        mysql_charset="utf8mb4",
    )

    # --- conversation_messages: the four messageType timeline ---
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        # Monotonic sort cursor; server-issued so replays are deterministic.
        sa.Column("sort_cursor", sa.BigInteger(), nullable=False),
        # JSON payload varies by messageType: question fields, draft content,
        # confirmation presentationState + canonical value, tool taskId.
        sa.Column("payload", sa.JSON(), nullable=False),
        # Optional cross-message linkage (e.g. CONFIRMATION_CARD -> USER_DRAFT).
        sa.Column("refers_to_message_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "message_type IN ('AGENT_PROMPT','USER_DRAFT','CONFIRMATION_CARD','TOOL_CARD')",
            name="ck_conv_msg_type",
        ),
        sa.CheckConstraint(
            "stage IN ('PROJECT_TEMPLATE','GEOGRAPHY_WEATHER','BUILDING_FLOOR',"
            "'AREA_PROCESS','PROCESS_ENVIRONMENT','COOLING_INPUT',"
            "'SCHEDULE_STORAGE','REVIEW')",
            name="ck_conv_msg_stage",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
            name="fk_conv_msg_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE", name="fk_conv_msg_project"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "sort_cursor", name="uq_conv_msg_conversation_cursor"
        ),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_conv_msg_conversation_cursor",
        "conversation_messages",
        ["conversation_id", "sort_cursor"],
    )
    op.create_index("ix_conv_msg_project", "conversation_messages", ["project_id"])

    # --- conversation_drafts: USER_DRAFT content with CAS ---
    op.create_table(
        "conversation_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        # Stable scope key, e.g. 'area:zone-1:area-m2'.
        sa.Column("scope_key", sa.String(length=128), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE", name="fk_conv_draft_project"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="RESTRICT", name="fk_conv_draft_actor"
        ),
        sa.PrimaryKeyConstraint("id"),
        # One draft per (project, actor, scope).
        sa.UniqueConstraint(
            "project_id", "actor_id", "scope_key", name="uq_conv_draft_scope"
        ),
        mysql_charset="utf8mb4",
    )

    # --- confirmation_challenges: impact + warning token lifecycle ---
    op.create_table(
        "confirmation_challenges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("question_key", sa.String(length=128), nullable=False),
        sa.Column("canonical_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("expected_input_revision", sa.Integer(), nullable=False),
        # impact_token is one-time; consumed_at set on first confirm regardless
        # of outcome (COMMITTED/BLOCKED/WARNING). Null until consumed.
        sa.Column("impact_token_hash", sa.String(length=64), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        # Warning path: warning_challenge_id is set when first confirm yields
        # WARNING_CONFIRMATION; reason-bound token issued after reasons submit.
        sa.Column("warning_codes", sa.JSON(), nullable=True),
        sa.Column("warning_challenge_hash", sa.String(length=64), nullable=True),
        sa.Column("warning_reasons", sa.JSON(), nullable=True),
        sa.Column("warning_confirmation_token_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE", name="fk_confch_project"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
            name="fk_confch_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="RESTRICT", name="fk_confch_actor"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("impact_token_hash", name="uq_confch_impact_token"),
        sa.UniqueConstraint(
            "warning_challenge_hash", name="uq_confch_warning_challenge"
        ),
        sa.UniqueConstraint(
            "warning_confirmation_token_hash", name="uq_confch_warning_confirm_token"
        ),
        mysql_charset="utf8mb4",
    )

    # --- conversation_audits: immutable per-COMMITTED audit ---
    op.create_table(
        "conversation_audits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("question_key", sa.String(length=128), nullable=False),
        sa.Column("field_path", sa.String(length=128), nullable=False),
        sa.Column("old_canonical_value", sa.JSON(), nullable=True),
        sa.Column("new_canonical_value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("warning_reasons", sa.JSON(), nullable=True),
        sa.Column("revision_before", sa.Integer(), nullable=False),
        sa.Column("revision_after", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('USER_INPUT','TEMPLATE_DEFAULT','ENGINEER_OVERRIDE','ADMIN_OVERRIDE')",
            name="ck_conv_audit_source",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE", name="fk_conv_audit_project"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
            name="fk_conv_audit_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="RESTRICT", name="fk_conv_audit_actor"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_conv_audit_project_revision",
        "conversation_audits",
        ["project_id", "revision_after"],
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order. We do NOT explicitly drop
    # indexes first: MySQL 8.x errors (1553) when dropping an index that
    # backs a foreign key, but DROP TABLE cascades all of a table's
    # indexes safely. drop_index is therefore omitted.
    op.drop_table("conversation_audits")
    op.drop_table("confirmation_challenges")
    op.drop_table("conversation_drafts")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
