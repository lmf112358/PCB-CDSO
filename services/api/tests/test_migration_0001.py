"""Migration 0001 downgrade regression test.

Migration 0001's downgrade failed on MySQL 8.x with:
  OperationalError: (1553, "Cannot drop index 'ix_audit_events_actor_user_id':
  needed in a foreign key constraint")

The index backs the audit_events.actor_user_id foreign key; MySQL forbids
dropping it while the FK still references the column. The fix is to drop the
foreign key before the index (or let DROP TABLE cascade). This test pins the
behavior against future regressions and uses a real MySQL server because
SQLite (the rest of the suite) does not enforce the FK-index coupling.

Skipped when MySQL is unreachable.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "services" / "api"

TEST_DB_NAME = "pcb_cdso_migration_test_0001"


def _mysql_url(database: str | None) -> str:
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
class Migration0001DowngradeTest(unittest.TestCase):
    """Migration 0001 must be reversible on MySQL (regression for FK-index bug)."""

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
        # Start each test from a clean base.
        _run_alembic(self.db_url, "downgrade", "base")

    def test_upgrade_then_downgrade_base_succeeds(self) -> None:
        up = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, up.returncode, up.stdout + up.stderr)

        down = _run_alembic(self.db_url, "downgrade", "base")
        self.assertEqual(0, down.returncode, down.stdout + down.stderr)

        inspector = inspect(create_engine(self.db_url))
        user_tables = set(inspector.get_table_names()) - {"alembic_version"}
        self.assertEqual(set(), user_tables)

    def test_downgrade_then_reupgrade_roundtrip(self) -> None:
        """upgrade -> downgrade -> upgrade must produce a clean schema again."""
        _run_alembic(self.db_url, "upgrade", "head")
        down = _run_alembic(self.db_url, "downgrade", "base")
        self.assertEqual(0, down.returncode, down.stdout + down.stderr)

        up2 = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, up2.returncode, up2.stdout + up2.stderr)

        inspector = inspect(create_engine(self.db_url))
        user_tables = set(inspector.get_table_names()) - {"alembic_version"}
        self.assertEqual({"users", "audit_events"}, user_tables)


if __name__ == "__main__":
    unittest.main()
