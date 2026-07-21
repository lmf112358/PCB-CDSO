"""Migration 0002 acceptance tests.

These tests validate the Alembic migration file itself (not the ORM models),
because the migration is the authoritative database contract and must remain
reversible. They run against a real MySQL server on an isolated scratch
database to avoid polluting the development schema.

Skipped automatically when MySQL is unreachable so the rest of the suite
stays deterministic. M1 acceptance runs these tests against a live MySQL per
docs/testing/plans/M1-test-plan.md.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "services" / "api"

TEST_DB_NAME = "pcb_cdso_migration_test_0002"


def _mysql_url(database: str | None) -> str:
    """Build a MySQL URL pointing at the test server.

    The development compose stack does not publish MySQL ports to the host by
    default, so set PCB_CDSO_TEST_MYSQL_* (host/port/user/password) to point
    at a reachable server (e.g. `docker compose exec mysql` or a published
    port mapping).
    """
    host = os.environ.get("PCB_CDSO_TEST_MYSQL_HOST", "127.0.0.1")
    port = os.environ.get("PCB_CDSO_TEST_MYSQL_PORT", "33306")
    user = os.environ.get("PCB_CDSO_TEST_MYSQL_USER", "pcb_cdso")
    password = os.environ.get("PCB_CDSO_TEST_MYSQL_PASSWORD", "local_only_replace_me")
    db_part = f"/{database}" if database else ""
    return f"mysql+pymysql://{user}:{password}@{host}:{port}{db_part}?charset=utf8mb4"


def _can_connect_mysql() -> bool:
    try:
        engine = create_engine(_mysql_url(None), pool_pre_ping=True)
        with engine.connect():
            return True
    except Exception:
        return False


def _run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PCB_CDSO_DATABASE_URL"] = database_url
    return subprocess.run(
        ["python", "-m", "alembic", *args],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@unittest.skipUnless(_can_connect_mysql(), "MySQL not reachable; set PCB_CDSO_TEST_MYSQL_* to enable")
class Migration0002Test(unittest.TestCase):
    """Validate migration 0002 forward, reverse, and forward-again.

    Each test method runs against the same isolated scratch database, reset
    to base in setUp so tests stay independent.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.server_engine = create_engine(_mysql_url(None))
        with cls.server_engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`"))
            connection.execute(
                text(f"CREATE DATABASE `{TEST_DB_NAME}` DEFAULT CHARSET utf8mb4")
            )
            connection.commit()
        cls.db_url = _mysql_url(TEST_DB_NAME)

    @classmethod
    def tearDownClass(cls) -> None:
        with cls.server_engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`"))
            connection.commit()

    def setUp(self) -> None:
        result = _run_alembic(self.db_url, "downgrade", "base")
        assert result.returncode == 0, result.stdout + result.stderr

    # ----- structural tests -----

    def test_upgrade_creates_all_m1_tables(self) -> None:
        result = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        inspector = inspect(create_engine(self.db_url))
        tables = set(inspector.get_table_names())
        required = {
            "users",
            "audit_events",
            "auth_sessions",
            "templates",
            "template_versions",
            "projects",
            "idempotency_records",
            "tasks",
            "outbox_events",
            "weather_dispatch_probe",
            "weather_task_executions",
        }
        missing = required - tables
        self.assertFalse(missing, f"migration 0002 missing tables: {sorted(missing)}")

    def test_users_table_gains_m1_columns(self) -> None:
        result = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        inspector = inspect(create_engine(self.db_url))
        columns = {col["name"] for col in inspector.get_columns("users")}
        for required in {"locale", "theme", "password_changed_at"}:
            self.assertIn(
                required,
                columns,
                f"users must gain column {required} in migration 0002",
            )

    def test_auth_sessions_has_revocation_and_uniqueness(self) -> None:
        result = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        inspector = inspect(create_engine(self.db_url))
        columns = {col["name"] for col in inspector.get_columns("auth_sessions")}
        for required in {
            "id",
            "user_id",
            "token_hash",
            "refresh_token_hash",
            "issued_at",
            "last_seen_at",
            "expires_at",
            "revoked_at",
            "created_at",
        }:
            self.assertIn(required, columns)

        unique_names = {uc["name"] for uc in inspector.get_unique_constraints("auth_sessions")}
        self.assertIn("uq_auth_sessions_token_hash", unique_names)
        self.assertIn("uq_auth_sessions_refresh_token_hash", unique_names)

    def test_idempotency_records_unique_is_actor_scoped_without_hash(self) -> None:
        """Design section 7: only (actor_id, key, scope); hash never unique."""
        _run_alembic(self.db_url, "upgrade", "head")
        inspector = inspect(create_engine(self.db_url))
        named = {
            uc["name"]: tuple(uc["column_names"])
            for uc in inspector.get_unique_constraints("idempotency_records")
        }
        self.assertIn("uq_idempotency_actor_key", named)
        self.assertEqual(
            ("actor_id", "idempotency_key", "scope"),
            named["uq_idempotency_actor_key"],
        )
        hash_unique = [
            name for name, cols in named.items() if "canonical_request_hash" in cols
        ]
        self.assertEqual(
            [], hash_unique, "canonical_request_hash must NOT be in any unique constraint"
        )

    def test_outbox_has_undispatched_index(self) -> None:
        _run_alembic(self.db_url, "upgrade", "head")
        inspector = inspect(create_engine(self.db_url))
        index_names = {idx["name"] for idx in inspector.get_indexes("outbox_events")}
        self.assertIn("ix_outbox_undispatched", index_names)

    def test_weather_dispatch_probe_pk_is_effect_key(self) -> None:
        _run_alembic(self.db_url, "upgrade", "head")
        inspector = inspect(create_engine(self.db_url))
        pk = inspector.get_pk_constraint("weather_dispatch_probe")
        self.assertEqual(["effect_key"], pk["constrained_columns"])

    # ----- constraint behavior tests -----

    def _seed_project(self, engine) -> None:
        """Insert prerequisite rows so a task row can reference them."""
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, role, is_active, locale, theme) "
                    "VALUES ('u1','a@b.com','h','ADMIN',1,'zh-CN','light')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO templates (id, slug, display_name) VALUES ('t1','hdi','HDI')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO template_versions (id, template_id, version_label, status, payload) "
                    "VALUES ('tv1','t1','v1.0.0','PUBLISHED', JSON_OBJECT())"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO projects (id, name, owner_id, template_version_id, country_code, "
                    "admin_area, city, timezone, status, input_revision, ownership_version) "
                    "VALUES ('p1','n','u1','tv1','CN','Guangdong','Shenzhen','Asia/Shanghai',"
                    "'ACTIVE',1,1)"
                )
            )

    def test_tasks_accepts_dispatch_pending_status(self) -> None:
        _run_alembic(self.db_url, "upgrade", "head")
        engine = create_engine(self.db_url)
        self._seed_project(engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tasks (id, project_id, task_type, input_revision, status, "
                    "status_version, progress, processed, total, retryable) "
                    "VALUES ('tk1','p1','WEATHER_HISTORY_FETCH',1,'DISPATCH_PENDING',1,0,0,0,0)"
                )
            )

    def test_tasks_rejects_invalid_status(self) -> None:
        _run_alembic(self.db_url, "upgrade", "head")
        engine = create_engine(self.db_url)
        self._seed_project(engine)
        with self.assertRaises(Exception):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO tasks (id, project_id, task_type, input_revision, status, "
                        "status_version, progress, processed, total, retryable) "
                        "VALUES ('tk1','p1','WEATHER_HISTORY_FETCH',1,'INVALID',1,0,0,0,0)"
                    )
                )

    # ----- reversibility -----

    def test_migration_is_reversible(self) -> None:
        up1 = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, up1.returncode, up1.stdout + up1.stderr)

        down = _run_alembic(self.db_url, "downgrade", "base")
        self.assertEqual(0, down.returncode, down.stdout + down.stderr)

        inspector = inspect(create_engine(self.db_url))
        tables_after_downgrade = set(inspector.get_table_names()) - {"alembic_version"}
        m1_tables = {
            "auth_sessions",
            "templates",
            "template_versions",
            "projects",
            "idempotency_records",
            "tasks",
            "outbox_events",
            "weather_dispatch_probe",
            "weather_task_executions",
        }
        leftover = m1_tables & tables_after_downgrade
        self.assertFalse(leftover, f"downgrade left M1 tables: {sorted(leftover)}")
        # 0001 tables are dropped too when going to base.
        self.assertNotIn("users", tables_after_downgrade)

        up2 = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, up2.returncode, up2.stdout + up2.stderr)


if __name__ == "__main__":
    unittest.main()
