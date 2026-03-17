"""Tests for Shadow Mirror base schema, init process, and event_log triggers."""

from pathlib import Path

from skene.growth_loops.push import (
    _build_trigger_function_sql,
    build_migration_sql,
    ensure_base_schema_migration,
)
from skene.growth_loops.schema_sql import BASE_SCHEMA_SQL, notify_event_log_sql


class TestBaseSchemaSQL:
    def test_contains_all_tables(self):
        for table in ("event_log", "failed_events", "enrichment_map"):
            assert table in BASE_SCHEMA_SQL

    def test_enrichment_map_has_metadata_key_and_enrich_sql(self):
        assert "metadata_key" in BASE_SCHEMA_SQL
        assert "enrich_sql" in BASE_SCHEMA_SQL

    def test_enrich_event_trigger_and_notify_webhook(self):
        assert "enrich_event" in BASE_SCHEMA_SQL
        assert "notify_event_log" in BASE_SCHEMA_SQL
        assert "pg_net" in BASE_SCHEMA_SQL

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
        assert "enrichment_map" in content

    def test_overwrites_when_already_exists(self, tmp_path: Path) -> None:
        first = ensure_base_schema_migration(tmp_path)
        assert first is not None
        second = ensure_base_schema_migration(tmp_path)
        assert second is not None
        assert second == first
        # Only one migration file
        migrations = list((tmp_path / "supabase" / "migrations").glob("*skene_growth_schema*.sql"))
        assert len(migrations) == 1


class TestEventLogTriggers:
    """Triggers INSERT into event_log, not pg_net."""

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
        loops = [
            {
                "loop_id": "x",
                "requirements": {
                    "telemetry": [{"type": "supabase", "table": "t", "properties": ["id"]}],
                },
            }
        ]
        migration = build_migration_sql(loops)
        assert "event_log" in migration
        assert "CREATE EXTENSION IF NOT EXISTS pg_net" not in migration
        assert "skene_growth.actions" not in migration
        assert "skene.actions" not in migration


class TestNotifyEventLogOverride:
    def test_notify_event_log_sql_includes_baked_url(self) -> None:
        sql = notify_event_log_sql("https://skene.ai", "my-secret")
        assert "https://skene.ai/api/v1/cloud/ingest/db-trigger" in sql
        assert "my-secret" in sql
        assert "net.http_post" in sql
        assert "x-skene-secret" in sql

    def test_notify_event_log_sql_avoids_duplicate_path_when_full_url_given(self) -> None:
        """Full upstream ingest URL (with db-trigger path) must not get path appended again."""
        full_url = "https://example.com/api/v1/cloud/ingest/db-trigger"
        sql = notify_event_log_sql(full_url, "secret")
        assert full_url in sql
        # Must not duplicate the path segment
        assert "db-trigger/api/v1" not in sql
        assert "db-trigger/db-trigger" not in sql

    def test_default_local_upstream_ingest_url_in_migration(self) -> None:
        """When --local is used without URL, default uses https://www.skene.ai."""
        loops = [
            {
                "loop_id": "x",
                "requirements": {
                    "telemetry": [{"type": "supabase", "table": "t", "properties": ["id"]}],
                },
            }
        ]
        migration = build_migration_sql(loops, forward_url="https://www.skene.ai")
        assert "https://www.skene.ai/api/v1/cloud/ingest/db-trigger" in migration
