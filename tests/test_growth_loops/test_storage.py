"""Tests for growth loop storage utilities."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from skene_growth.growth_loops.storage import (
    derive_loop_id,
    derive_loop_name,
    generate_loop_definition_with_llm,
    generate_timestamped_filename,
    sanitize_filename,
    write_growth_loop_json,
)


class TestDeriveLoopName:
    """Tests for derive_loop_name function."""

    def test_extracts_first_line(self):
        """Should extract the first non-empty line from next_build."""
        technical_execution = {"next_build": "Discovery Engine\nA powerful search feature\nWith advanced filtering"}
        result = derive_loop_name(technical_execution)
        assert result == "Discovery Engine"

    def test_handles_leading_whitespace(self):
        """Should handle leading/trailing whitespace."""
        technical_execution = {"next_build": "  \n  \n  Phase 1: Share Flag  \n  Other content  "}
        result = derive_loop_name(technical_execution)
        assert result == "Phase 1: Share Flag"

    def test_fallback_on_empty(self):
        """Should return fallback if next_build is empty."""
        technical_execution = {"next_build": "   \n  \n  "}
        result = derive_loop_name(technical_execution)
        assert result == "growth_loop"

    def test_fallback_on_missing(self):
        """Should return fallback if next_build is missing."""
        technical_execution = {}
        result = derive_loop_name(technical_execution)
        assert result == "growth_loop"


class TestDeriveLoopId:
    """Tests for derive_loop_id function."""

    def test_converts_to_snake_case(self):
        """Should convert human-readable names to snake_case."""
        assert derive_loop_id("Phase 1: Share Flag") == "share_flag"
        assert derive_loop_id("Phase 2: Discovery Engine") == "discovery_engine"
        assert derive_loop_id("Discovery Engine") == "discovery_engine"
        assert derive_loop_id("Auto-Commit Improve Mode") == "auto_commit_improve_mode"

    def test_removes_special_characters(self):
        """Should remove special characters."""
        assert derive_loop_id("Feature: Test (Alpha)") == "feature_test_alpha"
        assert derive_loop_id("User@Authentication") == "userauthentication"

    def test_collapses_multiple_underscores(self):
        """Should collapse multiple underscores."""
        assert derive_loop_id("Feature___With___Spaces") == "feature_with_spaces"

    def test_strips_leading_trailing_underscores(self):
        """Should strip leading/trailing underscores."""
        assert derive_loop_id("_Feature_") == "feature"
        assert derive_loop_id("__Test__") == "test"

    def test_handles_empty_string(self):
        """Should return fallback for empty string."""
        assert derive_loop_id("") == "growth_loop"
        assert derive_loop_id("   ") == "growth_loop"

    def test_handles_only_special_chars(self):
        """Should return fallback when only special chars remain."""
        assert derive_loop_id("!!!@@@") == "growth_loop"

    def test_removes_phase_prefixes(self):
        """Should remove phase prefixes from loop IDs."""
        assert derive_loop_id("Phase 1: Share Flag") == "share_flag"
        assert derive_loop_id("Phase 2: Discovery Engine") == "discovery_engine"
        assert derive_loop_id("Phase 3: Auto-Commit") == "auto_commit"
        assert derive_loop_id("Phase_1_Test") == "test"
        assert derive_loop_id("phase2_feature") == "feature"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_replaces_path_separators(self):
        """Should replace path separators with underscore."""
        assert sanitize_filename("path/to/file") == "path_to_file"
        assert sanitize_filename("path\\to\\file") == "path_to_file"

    def test_replaces_illegal_characters(self):
        """Should replace illegal filename characters."""
        assert sanitize_filename('file:name*with?illegal"chars<>|') == "file_name_with_illegal_chars___"

    def test_collapses_whitespace(self):
        """Should collapse whitespace to single underscores."""
        assert sanitize_filename("file   with   spaces") == "file_with_spaces"
        assert sanitize_filename("file\t\nwith\twhitespace") == "file_with_whitespace"

    def test_enforces_max_length(self):
        """Should enforce max length."""
        long_name = "a" * 100
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) == 50

    def test_strips_trailing_underscores_after_truncation(self):
        """Should strip trailing underscores after truncation."""
        name = "a" * 45 + "_" * 10
        result = sanitize_filename(name, max_length=50)
        assert not result.endswith("_")
        assert len(result) <= 50

    def test_handles_unicode(self):
        """Should handle unicode characters safely."""
        result = sanitize_filename("file_with_émojis_😀")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_fallback_on_empty(self):
        """Should return fallback if result is empty."""
        assert sanitize_filename("") == "growth_loop"
        assert sanitize_filename("___") == "growth_loop"


class TestGenerateTimestampedFilename:
    """Tests for generate_timestamped_filename function."""

    def test_generates_timestamped_filename(self):
        """Should generate filename with timestamp."""
        result = generate_timestamped_filename("discovery_engine")
        assert result.endswith("_discovery_engine.json")
        assert result[:-len("_discovery_engine.json")].replace("_", "").isdigit()

    def test_unique_timestamps(self):
        """Should generate unique filenames on repeated calls."""
        result1 = generate_timestamped_filename("test_loop")
        time.sleep(1.1)  # Ensure timestamp differs (second precision)
        result2 = generate_timestamped_filename("test_loop")
        assert result1 != result2

    def test_format_matches_spec(self):
        """Should match format: YYYYMMDD_HHMMSS_<loop_id>.json"""
        result = generate_timestamped_filename("test_loop")
        # Should have format: 20260203_143022_test_loop.json
        parts = result.replace(".json", "").split("_")
        assert len(parts) >= 3  # YYYYMMDD, HHMMSS, loop_id (may have underscores)
        assert len(parts[0]) == 8 and parts[0].isdigit()  # YYYYMMDD
        assert len(parts[1]) == 6 and parts[1].isdigit()  # HHMMSS


class TestWriteGrowthLoopJson:
    """Tests for write_growth_loop_json function."""

    def test_creates_growth_loops_directory(self, tmp_path):
        """Should create growth-loops directory."""
        payload = {"loop_id": "test", "name": "Test"}
        write_growth_loop_json(base_dir=tmp_path, filename="test.json", payload=payload)

        loops_dir = tmp_path / "growth-loops"
        assert loops_dir.exists()
        assert loops_dir.is_dir()

    def test_writes_json_file(self, tmp_path):
        """Should write JSON file with correct content."""
        payload = {"loop_id": "test_loop", "name": "Test Loop", "data": [1, 2, 3]}
        result_path = write_growth_loop_json(base_dir=tmp_path, filename="test.json", payload=payload)

        assert result_path.exists()
        assert result_path.name == "test.json"

        # Verify content
        written_data = json.loads(result_path.read_text())
        assert written_data == payload

    def test_pretty_prints_json(self, tmp_path):
        """Should pretty-print JSON with indentation."""
        payload = {"loop_id": "test", "nested": {"key": "value"}}
        result_path = write_growth_loop_json(base_dir=tmp_path, filename="test.json", payload=payload)

        content = result_path.read_text()
        assert "  " in content  # Check for indentation
        assert content.endswith("\n")  # Check for trailing newline

    def test_handles_unicode(self, tmp_path):
        """Should handle unicode in payload."""
        payload = {"loop_id": "test", "description": "Tëst with émojis 😀"}
        result_path = write_growth_loop_json(base_dir=tmp_path, filename="test.json", payload=payload)

        written_data = json.loads(result_path.read_text(encoding="utf-8"))
        assert written_data["description"] == "Tëst with émojis 😀"

    def test_collision_handling(self, tmp_path):
        """Should handle multiple writes with different timestamps."""
        payload1 = {"loop_id": "test1", "name": "Test 1"}
        payload2 = {"loop_id": "test2", "name": "Test 2"}

        path1 = write_growth_loop_json(base_dir=tmp_path, filename="test_20260203_120000.json", payload=payload1)
        path2 = write_growth_loop_json(base_dir=tmp_path, filename="test_20260203_120001.json", payload=payload2)

        assert path1.exists()
        assert path2.exists()
        assert path1 != path2

        # Verify different content
        data1 = json.loads(path1.read_text())
        data2 = json.loads(path2.read_text())
        assert data1["name"] == "Test 1"
        assert data2["name"] == "Test 2"


class TestGenerateLoopDefinitionWithLlm:
    """Tests for generate_loop_definition_with_llm function."""

    @pytest.mark.asyncio
    async def test_generates_valid_schema(self):
        """Should generate a valid loop definition matching schema."""
        # Mock LLM that returns valid JSON
        mock_llm = MagicMock()
        mock_llm.generate_content = AsyncMock(
            return_value=json.dumps(
                {
                    "loop_id": "test_loop",
                    "name": "Test Loop",
                    "description": "A test loop",
                    "requirements": {
                        "files": [
                            {
                                "path": "test.py",
                                "purpose": "Test file",
                                "required": True,
                                "checks": [{"type": "exists", "pattern": "test.py", "description": "File exists"}],
                            }
                        ],
                        "functions": [{"file": "test.py", "name": "test_func", "required": True}],
                        "integrations": [{"type": "cli_flag", "description": "--test flag", "required": True}],
                        "telemetry": [
                            {
                                "action_name": "document_created",
                                "table": "documents",
                                "operation": "INSERT",
                                "description": "Tracks when a document is created",
                                "properties": ["workspace_id", "id"],
                            }
                        ],
                    },
                    "dependencies": [],
                    "verification_commands": ["echo test"],
                    "test_coverage": {"unit_tests": [], "integration_tests": [], "manual_tests": []},
                    "metrics": {"data_actions": ["document_created"], "success_criteria": ["Test success"]},
                }
            )
        )

        result = await generate_loop_definition_with_llm(
            llm=mock_llm,
            technical_execution={"next_build": "Test feature", "confidence": "95%"},
            plan_path=Path("/tmp/plan.md"),
            codebase_path=Path("/tmp/code"),
        )

        # Verify required fields
        assert result["loop_id"] == "test_loop"
        assert result["name"] == "Test Loop"
        assert "description" in result
        assert "requirements" in result
        assert "files" in result["requirements"]
        assert "functions" in result["requirements"]
        assert "integrations" in result["requirements"]
        assert "telemetry" in result["requirements"]
        assert "dependencies" in result
        assert "verification_commands" in result
        assert "test_coverage" in result
        assert "metrics" in result
        # Feature linking fields (added in Phase 2)
        assert "linked_feature" in result
        assert "linked_feature_id" in result
        assert "growth_pillars" in result

    @pytest.mark.asyncio
    async def test_handles_markdown_code_fences(self):
        """Should strip markdown code fences from LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate_content = AsyncMock(
            return_value='```json\n{"loop_id": "test", "name": "Test", "description": "Test"}\n```'
        )

        result = await generate_loop_definition_with_llm(
            llm=mock_llm,
            technical_execution={"next_build": "Test"},
            plan_path=Path("/tmp/plan.md"),
            codebase_path=Path("/tmp/code"),
        )

        # Function derives these from technical_execution["next_build"] = "Test"
        assert result["loop_id"] == "test"
        assert result["name"] == "Test"

    @pytest.mark.asyncio
    async def test_provides_fallback_on_json_error(self):
        """Should provide minimal valid definition on JSON parse error."""
        mock_llm = MagicMock()
        mock_llm.generate_content = AsyncMock(return_value="Invalid JSON {{{")

        result = await generate_loop_definition_with_llm(
            llm=mock_llm,
            technical_execution={"next_build": "Test feature\nWith description"},
            plan_path=Path("/tmp/plan.md"),
            codebase_path=Path("/tmp/code"),
        )

        # Should still have valid structure (derived from "Test feature")
        assert result["loop_id"] == "test_feature"
        assert result["name"] == "Test feature"
        assert "requirements" in result
        assert "dependencies" in result
        assert isinstance(result["requirements"]["files"], list)

    @pytest.mark.asyncio
    async def test_ensures_required_structure(self):
        """Should ensure required structure even if LLM omits fields."""
        mock_llm = MagicMock()
        mock_llm.generate_content = AsyncMock(
            return_value=json.dumps(
                {
                    "description": "Minimal loop",
                    # Missing loop_id, name, requirements, etc.
                }
            )
        )

        result = await generate_loop_definition_with_llm(
            llm=mock_llm,
            technical_execution={"next_build": "Test Loop Implementation"},
            plan_path=Path("/tmp/plan.md"),
            codebase_path=Path("/tmp/code"),
        )

        # Should add missing required fields (derived from "Test Loop Implementation")
        assert result["loop_id"] == "test_loop_implementation"
        assert result["name"] == "Test Loop Implementation"
        assert "requirements" in result
        assert "files" in result["requirements"]
        assert "dependencies" in result
        assert isinstance(result["dependencies"], list)
