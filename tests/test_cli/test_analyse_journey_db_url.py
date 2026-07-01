"""Tests for analyse-journey CLI helpers and --db-url integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from skene.analyzers.journey.pipeline import JourneyPipelineConfig
from skene.analyzers.schema_parsers.models import SchemaIndex
from skene.cli.commands.analyse_journey import _infer_product_name, _redact_db_url


class TestRedactDbUrl:
    """Test _redact_db_url password redaction."""

    def test_redacts_password(self):
        assert _redact_db_url("postgresql://user:secret@host:5432/mydb") == "postgresql://user:***@host:5432/mydb"

    def test_no_password_keeps_user(self):
        assert _redact_db_url("postgresql://user@host/mydb") == "postgresql://user@host/mydb"

    def test_preserves_scheme(self):
        assert _redact_db_url("postgresql+async://user:pass@host/db") == "postgresql+async://user:***@host/db"

    def test_handles_no_at_sign(self):
        # No credentials at all
        assert _redact_db_url("postgresql://host/db") == "postgresql://host/db"

    def test_handles_query_params(self):
        assert (
            _redact_db_url("postgresql://user:pass@host/db?sslmode=require")
            == "postgresql://user:***@host/db?sslmode=require"
        )

    def test_corrupt_url_returns_redacted(self):
        assert _redact_db_url("not-a-valid-url-at-all") == "<redacted>"


class TestInferProductName:
    """Test _infer_product_name heuristics."""

    def test_from_repo_root(self):
        assert _infer_product_name(Path("/home/user/my-app"), None) == "my-app"

    def test_from_schema_dir(self):
        assert _infer_product_name(None, Path("/data/schemas")) == "schemas"

    def test_from_db_url(self):
        assert _infer_product_name(None, None, "postgresql://user:pass@host/mydb") == "mydb"

    def test_from_db_url_no_path(self):
        assert _infer_product_name(None, None, "postgresql://user:pass@host") == "Product"

    def test_repo_takes_precedence_over_db(self):
        assert _infer_product_name(Path("/home/user/app"), None, "postgresql://host/db") == "app"

    def test_fallback_to_product(self):
        assert _infer_product_name(None, None, None) == "Product"


class TestJourneyPipelineConfigWithSchemaIndex:
    """Test JourneyPipelineConfig accepts schema_index."""

    def test_config_with_schema_index(self):
        index = SchemaIndex()
        cfg = JourneyPipelineConfig(
            repo_root=None,
            schema_dir=None,
            schema_index=index,
            product_name="Test",
        )
        assert cfg.schema_index is index
        assert cfg.schema_dir is None

    def test_config_rejects_schema_dir_and_schema_index(self):
        index = SchemaIndex()
        with pytest.raises(ValueError, match="mutually exclusive"):
            JourneyPipelineConfig(
                repo_root=None,
                schema_dir=Path("/tmp/schemas"),
                schema_index=index,
                product_name="Test",
            )

    def test_config_with_repo_and_schema_index(self):
        index = SchemaIndex()
        cfg = JourneyPipelineConfig(
            repo_root=Path("/tmp/repo"),
            schema_dir=None,
            schema_index=index,
            product_name="Test",
        )
        assert cfg.repo_root is not None
        assert cfg.schema_index is index
