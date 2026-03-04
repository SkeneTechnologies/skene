"""Tests for Shadow Mirror base schema, init process, and event_log triggers."""

from pathlib import Path

import pytest

from skene_growth.growth_loops.deploy import (
    _build_trigger_function_sql,
    build_migration_sql,
    ensure_base_schema_migration,
    ensure_processor_migration,
)
from skene_growth.growth_loops.processor_sql import PROCESSOR_SQL
from skene_growth.growth_loops.schema_sql import BASE_SCHEMA_SQL


class TestBaseSchemaSQL:
    def test_contains_all_tables(self):
        for table in ("event_log", "growth_loops", "loop_executions", "attribution", "failed_events"):
            assert table in BASE_SCHEMA_SQL

    def test_uses_idempotent_ddl(self):
        assert "CREATE SCHEMA IF NOT EXISTS" in BASE_SCHEMA_SQL
        assert "CREATE TABLE IF NOT EXISTS" in BASE_SCHEMA_SQL


class TestEnsureBaseSchemaMigration:
    def test_creates_migration_when_missing(self, tmp_path: Path) -> None:
        out = ensure_base_schema_migration(tmp_path)
        assert out is not None
        assert out.exists()
        assert "skene_growth_schema" in out.name
        content = out.read_text()
        assert "event_log" in content
        assert "growth_loops" in content

    def test_skips_when_already_exists(self, tmp_path: Path) -> None:
        first = ensure_base_schema_migration(tmp_path)
        assert first is not None
        second = ensure_base_schema_migration(tmp_path)
        assert second is None
        # Only one migration file
        migrations = list((tmp_path / "supabase" / "migrations").glob("*skene_growth_schema*.sql"))
        assert len(migrations) == 1


class TestEventLogTriggers:
    """Phase 2: triggers INSERT into event_log, not pg_net."""

    def test_trigger_inserts_into_event_log(self) -> None:
        sql = _build_trigger_function_sql(
            loop_id="test_loop",
            action_name="test_action",
            table="api_keys",
            operation="INSERT",
            properties=["id", "workspace_id"],
        )
        assert "INSERT INTO skene_growth.event_log" in sql
        assert "api_keys.insert" in sql
        assert "net.http_post" not in sql
        assert "pg_net" not in sql

    def test_migration_has_no_pg_net_or_actions(self) -> None:
        loops = [{
            "loop_id": "x",
            "requirements": {
                "telemetry": [{"type": "supabase", "table": "t", "properties": ["id"]}],
            },
        }]
        migration = build_migration_sql(loops)
        assert "event_log" in migration
        assert "CREATE EXTENSION IF NOT EXISTS pg_net" not in migration
        assert "skene_growth.actions" not in migration

    def test_migration_seeds_growth_loops(self) -> None:
        loops = [{
            "loop_id": "my_loop",
            "requirements": {
                "telemetry": [{"type": "supabase", "table": "users", "operation": "INSERT"}],
            },
        }]
        migration = build_migration_sql(loops)
        assert "INSERT INTO skene_growth.growth_loops" in migration
        assert "my_loop_users_insert" in migration
        assert "users.insert" in migration


class TestProcessor:
    def test_processor_sql_creates_function(self) -> None:
        assert "process_events" in PROCESSOR_SQL
        assert "event_log" in PROCESSOR_SQL
        assert "growth_loops" in PROCESSOR_SQL

    def test_ensure_processor_migration_creates_file(self, tmp_path: Path) -> None:
        out = ensure_processor_migration(tmp_path)
        assert out is not None
        assert "skene_growth_processor" in out.name
