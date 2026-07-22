"""Migration 0003 acceptance tests (M2 conversation workspace).

Validates the Alembic migration itself against a real MySQL on an isolated
scratch database. Skipped when MySQL is unreachable.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "services" / "api"

TEST_DB_NAME = "pcb_cdso_migration_test_0003"


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
class Migration0003Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server_engine = create_engine(_mysql_url(None))
        with cls.server_engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`"))
            connection.execute(text(f"CREATE DATABASE `{TEST_DB_NAME}` DEFAULT CHARSET utf8mb4"))
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

    def test_upgrade_creates_conversation_tables(self) -> None:
        result = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        inspector = inspect(create_engine(self.db_url))
        tables = set(inspector.get_table_names())
        for required in {
            "conversations",
            "conversation_messages",
            "conversation_drafts",
            "confirmation_challenges",
            "conversation_audits",
        }:
            self.assertIn(required, tables, f"missing M2 table: {required}")

    def test_message_type_check_rejects_invalid(self) -> None:
        _run_alembic(self.db_url, "upgrade", "head")
        engine = create_engine(self.db_url)
        # Seed prerequisites via raw SQL.
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (id,email,password_hash,role,is_active,locale,theme) VALUES ('u1','a@b.com','h','ADMIN',1,'zh-CN','light')"))
            conn.execute(text("INSERT INTO templates (id,slug,display_name) VALUES ('t1','hdi','HDI')"))
            conn.execute(text("INSERT INTO template_versions (id,template_id,version_label,status,payload) VALUES ('tv1','t1','v1','PUBLISHED',JSON_OBJECT())"))
            conn.execute(text("INSERT INTO projects (id,name,owner_id,template_version_id,country_code,admin_area,city,timezone,status,input_revision,ownership_version) VALUES ('p1','n','u1','tv1','CN','X','Y','Asia/Shanghai','ACTIVE',1,1)"))
            conn.execute(text("INSERT INTO conversations (id,project_id,input_revision,stage_state) VALUES ('c1','p1',1,JSON_OBJECT())"))
            # Invalid message_type must be rejected.
            with self.assertRaises(Exception):
                conn.execute(text("INSERT INTO conversation_messages (id,conversation_id,project_id,message_type,stage,sort_cursor,payload) VALUES ('m1','c1','p1','INVALID','PROJECT_TEMPLATE',1,JSON_OBJECT())"))

    def test_draft_scope_unique_per_project_actor(self) -> None:
        _run_alembic(self.db_url, "upgrade", "head")
        engine = create_engine(self.db_url)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (id,email,password_hash,role,is_active,locale,theme) VALUES ('u1','a@b.com','h','ENGINEER',1,'zh-CN','light')"))
            conn.execute(text("INSERT INTO templates (id,slug,display_name) VALUES ('t1','hdi','HDI')"))
            conn.execute(text("INSERT INTO template_versions (id,template_id,version_label,status,payload) VALUES ('tv1','t1','v1','PUBLISHED',JSON_OBJECT())"))
            conn.execute(text("INSERT INTO projects (id,name,owner_id,template_version_id,country_code,admin_area,city,timezone,status,input_revision,ownership_version) VALUES ('p1','n','u1','tv1','CN','X','Y','Asia/Shanghai','ACTIVE',1,1)"))
            conn.execute(text("INSERT INTO conversation_drafts (id,project_id,actor_id,scope_key,draft_version,content) VALUES ('d1','p1','u1','area:z1:m2',1,JSON_OBJECT())"))
            # Duplicate (project, actor, scope_key) must be rejected.
            with self.assertRaises(Exception):
                conn.execute(text("INSERT INTO conversation_drafts (id,project_id,actor_id,scope_key,draft_version,content) VALUES ('d2','p1','u1','area:z1:m2',1,JSON_OBJECT())"))

    def test_migration_is_reversible(self) -> None:
        up1 = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, up1.returncode, up1.stdout + up1.stderr)
        # Downgrade to 0002 keeps M1 tables, drops M2 tables.
        down = _run_alembic(self.db_url, "downgrade", "0002_m1_project_weather_dispatch")
        self.assertEqual(0, down.returncode, down.stdout + down.stderr)
        inspector = inspect(create_engine(self.db_url))
        tables = set(inspector.get_table_names()) - {"alembic_version"}
        m2_tables = {
            "conversations",
            "conversation_messages",
            "conversation_drafts",
            "confirmation_challenges",
            "conversation_audits",
        }
        self.assertFalse(m2_tables & tables, "M2 tables must be dropped on downgrade to 0002")
        # M1 table still present.
        self.assertIn("projects", tables)
        # Re-upgrade clean.
        up2 = _run_alembic(self.db_url, "upgrade", "head")
        self.assertEqual(0, up2.returncode, up2.stdout + up2.stderr)


if __name__ == "__main__":
    unittest.main()
