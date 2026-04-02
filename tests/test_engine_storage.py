"""Tests for engine.yaml storage and migration adapters."""

from pathlib import Path

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
        write_engine_document(engine_path, doc)
        loaded = load_engine_document(engine_path)
        assert loaded.version == 1
        assert loaded.subjects[0].key == "user"
        assert loaded.features[0].key == "welcome_email"


class TestEngineMerge:
    def test_merge_upserts_by_key(self):
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
        assert parse_source_to_db_event("public.documents.insert") == ("public", "documents", "INSERT")
        assert parse_source_to_db_event("public.documents.UPDATE") == ("public", "documents", "UPDATE")
        assert parse_source_to_db_event("invalid-source") is None

    def test_engine_features_to_loop_definitions_filters_by_action(self):
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
        assert telemetry["table"] == "documents"
        assert telemetry["operation"] == "INSERT"
        assert telemetry["properties"] == ["id", "owner_id"]

    def test_build_loops_to_supabase_writes_migration_file(self, tmp_path: Path):
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
