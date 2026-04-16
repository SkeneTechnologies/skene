"""Tests for engine validator."""

from pathlib import Path

import pytest

from skene.engine import EngineDocument, write_engine_document
from skene.validators.engine_validator import validate_engine


class TestEngineValidator:
    def test_fails_when_engine_missing(self, tmp_path: Path):
        """Returns a validation error when engine.yaml is absent."""
        result = validate_engine(tmp_path)
        assert not result.ok
        assert result.errors

    def test_code_only_feature_does_not_require_migration(self, tmp_path: Path):
        """Treats code-only features as valid without trigger migrations."""
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "user", "table": "auth.users", "kind": "actor"}],
                "features": [
                    {
                        "key": "code_only",
                        "name": "Code Only",
                        "source": "public.documents.insert",
                        "how_it_works": "Code-only behavior",
                        "match_intent": "docs",
                        "subject_state_analysis": {},
                    }
                ],
            }
        )
        write_engine_document(tmp_path / "skene" / "engine.yaml", doc, project_root=tmp_path)

        result = validate_engine(tmp_path)
        assert result.ok
        assert len(result.feature_checks) == 1
        assert result.feature_checks[0].action_required is False
        assert result.feature_checks[0].passed is True

    def test_action_feature_requires_expected_trigger(self, tmp_path: Path):
        """Marks actionable features valid when expected trigger/function exist."""
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "document", "table": "public.documents", "kind": "actor"}],
                "features": [
                    {
                        "key": "new_document_email",
                        "name": "New Document Email",
                        "source": "public.documents.insert",
                        "how_it_works": "Send email",
                        "match_intent": "docs",
                        "subject_state_analysis": {"subject_id_path": "id", "action_target_path": "owner_id"},
                        "action": {"use": "email", "config": {}},
                    }
                ],
            }
        )
        write_engine_document(tmp_path / "skene" / "engine.yaml", doc, project_root=tmp_path)

        migrations_dir = tmp_path / "supabase" / "migrations"
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "20260304151537_skene_triggers.sql").write_text(
            """
CREATE OR REPLACE FUNCTION skene_growth_fn_documents_INSERT_new_document_email()
RETURNS TRIGGER AS $$ BEGIN RETURN NULL; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS skene_growth_trg_documents_INSERT_new_document_email ON public.documents;
CREATE TRIGGER skene_growth_trg_documents_INSERT_new_document_email
AFTER INSERT ON public.documents
FOR EACH ROW
EXECUTE FUNCTION skene_growth_fn_documents_INSERT_new_document_email();
""".strip()
        )

        result = validate_engine(tmp_path)
        assert result.ok
        assert result.feature_checks[0].action_required is True
        assert result.feature_checks[0].migration_found is True

    def test_action_feature_detail_shows_latest_migration_plus_count(self, tmp_path: Path):
        """Reports the latest matching migration and extra match count."""
        sql = """
CREATE OR REPLACE FUNCTION skene_growth_fn_documents_INSERT_new_document_email()
RETURNS TRIGGER AS $$ BEGIN RETURN NULL; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS skene_growth_trg_documents_INSERT_new_document_email ON public.documents;
CREATE TRIGGER skene_growth_trg_documents_INSERT_new_document_email
AFTER INSERT ON public.documents
FOR EACH ROW
EXECUTE FUNCTION skene_growth_fn_documents_INSERT_new_document_email();
""".strip()
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "document", "table": "public.documents", "kind": "actor"}],
                "features": [
                    {
                        "key": "new_document_email",
                        "name": "New Document Email",
                        "source": "public.documents.insert",
                        "how_it_works": "Send email",
                        "match_intent": "docs",
                        "subject_state_analysis": {"subject_id_path": "id", "action_target_path": "owner_id"},
                        "action": {"use": "email", "config": {}},
                    }
                ],
            }
        )
        write_engine_document(tmp_path / "skene" / "engine.yaml", doc, project_root=tmp_path)
        migrations_dir = tmp_path / "supabase" / "migrations"
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "20260101000000_skene_triggers.sql").write_text(sql)
        (migrations_dir / "20260304151537_skene_triggers.sql").write_text(sql)

        result = validate_engine(tmp_path)
        assert result.ok
        assert result.feature_checks[0].detail == ("Found in: 20260304151537_skene_triggers.sql (+1)")

    def test_ignores_symlinked_migrations_outside_project(self, tmp_path: Path):
        """Ignores symlinked SQL files that resolve outside the migrations directory."""
        doc = EngineDocument.model_validate(
            {
                "version": 1,
                "subjects": [{"key": "document", "table": "public.documents", "kind": "actor"}],
                "features": [
                    {
                        "key": "new_document_email",
                        "name": "New Document Email",
                        "source": "public.documents.insert",
                        "how_it_works": "Send email",
                        "match_intent": "docs",
                        "subject_state_analysis": {"subject_id_path": "id", "action_target_path": "owner_id"},
                        "action": {"use": "email", "config": {}},
                    }
                ],
            }
        )
        write_engine_document(tmp_path / "skene" / "engine.yaml", doc, project_root=tmp_path)

        external_sql = tmp_path / "external.sql"
        external_sql.write_text(
            """
CREATE OR REPLACE FUNCTION skene_growth_fn_documents_INSERT_new_document_email()
RETURNS TRIGGER AS $$ BEGIN RETURN NULL; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER skene_growth_trg_documents_INSERT_new_document_email
AFTER INSERT ON public.documents
FOR EACH ROW
EXECUTE FUNCTION skene_growth_fn_documents_INSERT_new_document_email();
""".strip(),
            encoding="utf-8",
        )

        migrations_dir = tmp_path / "supabase" / "migrations"
        migrations_dir.mkdir(parents=True)
        symlink_path = migrations_dir / "20260304151537_skene_triggers.sql"
        try:
            symlink_path.symlink_to(external_sql)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation not supported in this environment")

        result = validate_engine(tmp_path)
        assert not result.ok
        assert result.feature_checks[0].migration_found is False
