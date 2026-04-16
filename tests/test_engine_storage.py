"""Tests for engine.yaml storage and migration adapters."""

from pathlib import Path

import pytest

from skene.engine import (
    EngineDocument,
    engine_features_to_loop_definitions,
    load_engine_document,
    merge_engine_documents,
    parse_source_to_db_event,
    write_engine_document,
)
from skene.growth_loops.push import build_loops_to_supabase


class TestEngineRoundTrip:
    def test_write_and_load_engine(self, tmp_path: Path):
        """Writes engine.yaml and loads it back without data loss."""
        engine_path = tmp_path / "skene" / "engine.yaml"
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "user", "table": "auth.users", "kind": "actor"}],
                "features": [
                    {
                        "key": "welcome_email",
                        "name": "Welcome Email",
                        "source": "public.users.insert",
                        "how_it_works": "Send welcome email",
                        "match_intent": "users table insert",
                        "subject_state_analysis": {
                            "lifecycle_subject": "user",
                            "subject_id_path": "id",
                            "action_target_path": "id",
                            "state": None,
                            "record_predicates": [],
                            "analysis_notes": "Welcome flow.",
                        },
                    }
                ],
            }
        )
        write_engine_document(engine_path, doc, project_root=tmp_path)
        loaded = load_engine_document(engine_path, project_root=tmp_path)
        assert loaded.version == 1
        assert loaded.subjects[0].key == "user"
        assert loaded.features[0].key == "welcome_email"


class TestEngineMerge:
    def test_merge_upserts_by_key(self):
        """Merges delta records by key while preserving deterministic ordering."""
        existing = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "user", "table": "auth.users", "kind": "actor"}],
                "features": [
                    {
                        "key": "welcome_email",
                        "name": "Welcome Email",
                        "source": "public.users.insert",
                        "how_it_works": "Send welcome email",
                        "match_intent": "users insert",
                        "subject_state_analysis": {},
                    }
                ],
            }
        )
        delta = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "document", "table": "public.documents", "kind": "actor"}],
                "features": [
                    {
                        "key": "welcome_email",
                        "name": "Welcome Email v2",
                        "source": "public.users.insert",
                        "how_it_works": "Updated behavior",
                        "match_intent": "users insert",
                        "subject_state_analysis": {},
                    },
                    {
                        "key": "new_document_email",
                        "name": "New Document Email",
                        "source": "public.documents.insert",
                        "how_it_works": "Notify owner",
                        "match_intent": "documents.owner_id",
                        "subject_state_analysis": {},
                        "action": {"use": "email", "config": {}},
                    },
                ],
            }
        )
        merged = merge_engine_documents(existing, delta)
        assert [s.key for s in merged.subjects] == ["document", "user"]
        assert [f.key for f in merged.features] == ["new_document_email", "welcome_email"]
        assert next(f for f in merged.features if f.key == "welcome_email").name == "Welcome Email v2"


class TestEngineSourceAndAdapter:
    def test_parse_source_to_db_event(self):
        """Parses valid sources and rejects malformed source strings."""
        assert parse_source_to_db_event("public.documents.insert") == ("public", "documents", "INSERT")
        assert parse_source_to_db_event("public.documents.UPDATE") == ("public", "documents", "UPDATE")
        assert parse_source_to_db_event("invalid-source") is None

    def test_engine_features_to_loop_definitions_filters_by_action(self):
        """Converts only actionable engine features into loop definitions."""
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "user", "table": "auth.users", "kind": "actor"}],
                "features": [
                    {
                        "key": "code_only_feature",
                        "name": "Code Only",
                        "source": "public.documents.insert",
                        "how_it_works": "No DB trigger needed",
                        "match_intent": "docs",
                        "subject_state_analysis": {},
                    },
                    {
                        "key": "db_trigger_feature",
                        "name": "DB Trigger",
                        "source": "public.documents.insert",
                        "how_it_works": "Needs DB trigger",
                        "match_intent": "docs",
                        "subject_state_analysis": {"subject_id_path": "id", "action_target_path": "owner_id"},
                        "action": {"use": "email", "config": {"template": "x"}},
                    },
                ],
            }
        )

        loops = engine_features_to_loop_definitions(doc)
        assert len(loops) == 1
        assert loops[0]["loop_id"] == "db_trigger_feature"
        telemetry = loops[0]["requirements"]["telemetry"][0]
        assert telemetry["schema"] == "public"
        assert telemetry["table"] == "documents"
        assert telemetry["operation"] == "INSERT"
        assert telemetry["properties"] == ["id", "owner_id"]

    def test_engine_features_to_loop_definitions_preserves_non_public_schema(self):
        """Includes schema in telemetry so migrations target the correct relation."""
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "user", "table": "auth.users", "kind": "actor"}],
                "features": [
                    {
                        "key": "auth_user_hook",
                        "name": "Auth User Hook",
                        "source": "auth.users.insert",
                        "how_it_works": "Track new auth users",
                        "match_intent": "auth users",
                        "subject_state_analysis": {"subject_id_path": "id"},
                        "action": {"use": "email", "config": {}},
                    }
                ],
            }
        )
        loops = engine_features_to_loop_definitions(doc)
        telemetry = loops[0]["requirements"]["telemetry"][0]
        assert telemetry["schema"] == "auth"
        assert telemetry["table"] == "users"

    def test_build_loops_to_supabase_writes_migration_file(self, tmp_path: Path):
        """Builds a Supabase trigger migration file from actionable loops."""
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "document", "table": "public.documents", "kind": "actor"}],
                "features": [
                    {
                        "key": "db_trigger_feature",
                        "name": "DB Trigger",
                        "source": "public.documents.insert",
                        "how_it_works": "Needs DB trigger",
                        "match_intent": "docs",
                        "subject_state_analysis": {"subject_id_path": "id"},
                        "action": {"use": "email", "config": {"template": "x"}},
                    }
                ],
            }
        )
        loops = engine_features_to_loop_definitions(doc)
        migration_path = build_loops_to_supabase(loops, tmp_path)
        assert migration_path.exists()
        assert migration_path.name.endswith("_skene_triggers.sql")
        sql = migration_path.read_text(encoding="utf-8")
        assert 'ON "public"."documents"' in sql
        assert "public.public.documents" not in sql

    def test_build_loops_to_supabase_qualifies_non_public_schema(self, tmp_path: Path):
        """Trigger DDL targets schema.table, not public.<table>, for non-public sources."""
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [],
                "features": [
                    {
                        "key": "auth_hook",
                        "name": "Auth Hook",
                        "source": "auth.users.insert",
                        "how_it_works": "Hook",
                        "match_intent": "auth",
                        "subject_state_analysis": {"subject_id_path": "id"},
                        "action": {"use": "email", "config": {}},
                    }
                ],
            }
        )
        loops = engine_features_to_loop_definitions(doc)
        migration_path = build_loops_to_supabase(loops, tmp_path)
        sql = migration_path.read_text(encoding="utf-8")
        assert 'ON "auth"."users"' in sql
        assert "skene_growth_trg_auth_users_INSERT_auth_hook" in sql


class TestEnginePathSafety:
    def test_load_rejects_paths_outside_project_root(self, tmp_path: Path):
        """Rejects engine loads that resolve outside the provided project root."""
        outside_engine_path = tmp_path.parent / "external" / "engine.yaml"
        outside_engine_path.parent.mkdir(parents=True, exist_ok=True)
        outside_engine_path.write_text("version: 1\nsubjects: []\nfeatures: []\n", encoding="utf-8")

        with pytest.raises(ValueError, match="escapes project root"):
            load_engine_document(outside_engine_path, project_root=tmp_path)

    def test_write_rejects_paths_outside_project_root(self, tmp_path: Path):
        """Rejects engine writes that resolve outside the provided project root."""
        outside_engine_path = tmp_path.parent / "external-write" / "engine.yaml"
        doc = EngineDocument.model_validate({"version": 1, "subjects": [], "features": []})

        with pytest.raises(ValueError, match="escapes project root"):
            write_engine_document(outside_engine_path, doc, project_root=tmp_path)
