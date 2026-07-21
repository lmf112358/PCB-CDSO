"""Add M1 project-weather-dispatch tables.

Revision ID: 0002_m1_project_weather_dispatch
Revises: 0001_users_audit
Create Date: 2026-07-22

Covers docs/architecture/m1-migration-0002-design.md:
- users: + locale, theme, password_changed_at
- auth_sessions, templates, template_versions, projects,
  idempotency_records, tasks, outbox_events, weather_dispatch_probe,
  weather_task_executions

Design decisions (tech lead 2026-07-21, see migration design section 7):
- idempotency_records has only (actor_id, idempotency_key, scope) unique;
  canonical_request_hash is NOT in any unique constraint.
- weather_task_executions is a separate 1:N table (not merged into tasks.stage).
- projects.ownership_version is frozen as a column but not used in M1.
- templates/template_versions ship as a minimal skeleton so projects can
  reference a PUBLISHED version; full lifecycle is P0_03 (future).

Constraints are named (uq_*, ck_*, fk_*, ix_*) so reconcilers, governance
tests and future migrations reference stable identifiers. CHECK constraints
use MySQL-compatible inline syntax; enum widening in M4+ goes through a new
migration, never by editing this file.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_m1_project_weather_dispatch"
down_revision: str | None = "0001_users_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: account preferences + password audit (M1) ---
    op.add_column(
        "users",
        sa.Column("locale", sa.String(length=8), nullable=False, server_default="zh-CN"),
    )
    op.add_column(
        "users",
        sa.Column("theme", sa.String(length=8), nullable=False, server_default="light"),
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint("ck_users_locale", "users", "locale IN ('zh-CN','en-US')")
    op.create_check_constraint("ck_users_theme", "users", "theme IN ('light','dark')")

    # --- auth_sessions (ADR-0002 server-revocable sessions) ---
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_auth_sessions_user"
        ),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
        sa.UniqueConstraint(
            "refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_auth_sessions_user_expires",
        "auth_sessions",
        ["user_id", "expires_at"],
    )

    # --- templates: minimal skeleton ---
    op.create_table(
        "templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_templates_slug"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )

    # --- template_versions: immutable published snapshot ---
    op.create_table(
        "template_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("version_label", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','ARCHIVED')",
            name="ck_template_versions_status",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["templates.id"], ondelete="RESTRICT",
            name="fk_template_versions_template",
        ),
        sa.UniqueConstraint(
            "template_id", "version_label", name="uq_template_versions_template_version"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_template_versions_status", "template_versions", ["status"]
    )

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("template_version_id", sa.String(length=36), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("admin_area", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_revision", sa.Integer(), nullable=False),
        sa.Column("ownership_version", sa.Integer(), nullable=False),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "country_code REGEXP '^[A-Z]{2}$'", name="ck_projects_country_code"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','ARCHIVED','SOFT_DELETED')",
            name="ck_projects_status",
        ),
        sa.CheckConstraint("input_revision > 0", name="ck_projects_input_revision"),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="RESTRICT", name="fk_projects_owner"
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["template_versions.id"],
            ondelete="RESTRICT",
            name="fk_projects_template_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_projects_owner_status", "projects", ["owner_id", "status"]
    )

    # --- idempotency_records: single actor-scoped unique key ---
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("canonical_request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result_project_id", sa.String(length=36), nullable=True),
        sa.Column("result_weather_task_id", sa.String(length=36), nullable=True),
        sa.Column("result_snapshot_ids", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','SUCCEEDED')", name="ck_idempotency_status"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="RESTRICT", name="fk_idempotency_actor"
        ),
        # Per design section 7: ONLY this unique key. canonical_request_hash
        # is intentionally excluded; hash comparison is application-layer.
        sa.UniqueConstraint(
            "actor_id", "idempotency_key", "scope", name="uq_idempotency_actor_key"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_idempotency_status_created",
        "idempotency_records",
        ["status", "created_at"],
    )

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("input_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("status_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_payload", sa.JSON(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('DISPATCH_PENDING','QUEUED','RUNNING','SUCCEEDED',"
            "'FAILED','CANCELLED','STALE')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "task_type IN ('WEATHER_HISTORY_FETCH')", name="ck_tasks_task_type"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="RESTRICT", name="fk_tasks_project"
        ),
        # Worker business dedup key: one task per (project, revision, type).
        sa.UniqueConstraint(
            "project_id", "input_revision", "task_type", name="uq_tasks_worker_dedup"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_tasks_status_updated", "tasks", ["status", "updated_at"])
    op.create_index("ix_tasks_project", "tasks", ["project_id"])

    # --- outbox_events ---
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("input_revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('WeatherFetchRequested')", name="ck_outbox_event_type"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], ondelete="RESTRICT", name="fk_outbox_task"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="RESTRICT", name="fk_outbox_project"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    # Reconciler scans undispatched rows by (dispatched_at, created_at).
    op.create_index(
        "ix_outbox_undispatched", "outbox_events", ["dispatched_at", "created_at"]
    )
    op.create_index("ix_outbox_task", "outbox_events", ["task_id"])

    # --- weather_dispatch_probe: M1 fake Worker effect ---
    op.create_table(
        "weather_dispatch_probe",
        sa.Column("effect_key", sa.String(length=160), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("input_revision", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("effect_key"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_weather_dispatch_probe_project",
        "weather_dispatch_probe",
        ["project_id"],
    )

    # --- weather_task_executions: 1:N with tasks ---
    op.create_table(
        "weather_task_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_payload", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','SUCCEEDED','FAILED')",
            name="ck_weather_exec_status",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], ondelete="RESTRICT", name="fk_weather_exec_task"
        ),
        sa.UniqueConstraint(
            "task_id", "attempt", name="uq_weather_exec_task_attempt"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_weather_exec_status", "weather_task_executions", ["status"]
    )


def downgrade() -> None:
    # Drop in reverse dependency order. Each table's FKs are dropped along
    # with the table (MySQL cascades), so we only need ordered drop_table.
    op.drop_table("weather_task_executions")
    op.drop_table("weather_dispatch_probe")
    op.drop_table("outbox_events")
    op.drop_table("tasks")
    op.drop_table("idempotency_records")
    op.drop_table("projects")
    op.drop_table("template_versions")
    op.drop_table("templates")
    op.drop_table("auth_sessions")

    # Remove the two CHECK constraints before dropping columns they govern.
    op.drop_constraint("ck_users_theme", "users", type_="check")
    op.drop_constraint("ck_users_locale", "users", type_="check")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "theme")
    op.drop_column("users", "locale")
