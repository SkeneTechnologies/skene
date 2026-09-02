"""Tests for activation plan generation flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skene.cli.analysis_helpers import run_generate_plan
from skene.cli.prompt_builder import (
    extract_executive_summary,
    extract_next_action,
    extract_technical_execution,
)


def test_extract_helpers_defensive_against_string_and_invalid_inputs(tmp_path: Path):
    """extract_* functions must not raise AttributeError when passed markdown text or non-existent paths."""
    assert extract_executive_summary("# Markdown content\n\nSome text") is None
    assert extract_next_action("Some string without path") is None
    assert extract_technical_execution("# Some header") is None

    # When pointing to a non-existent path
    non_existent = tmp_path / "non_existent.md"
    assert extract_executive_summary(non_existent) is None
    assert extract_next_action(non_existent) is None
    assert extract_technical_execution(non_existent) is None


@pytest.mark.asyncio
async def test_run_generate_plan_activation_mode(tmp_path: Path):
    """run_generate_plan with activation=True should succeed without crashing on string with_suffix."""
    manifest_file = tmp_path / "growth-manifest.json"
    manifest_file.write_text('{"project_name": "TestApp", "current_growth_features": []}')

    template_file = tmp_path / "growth-template.json"
    template_file.write_text('{"lifecycles": []}')

    output_path = tmp_path / "growth-plan.md"

    mock_llm = MagicMock()
    mock_llm.generate_content = AsyncMock(return_value="## Activation Memo\n\n1. Focus on onboarding flow.")

    with (
        patch("skene.llm.create_llm_client", return_value=mock_llm),
        patch("skene.cli.analysis_helpers.generate_todo_list", AsyncMock(return_value="- [ ] Implement welcome email")),
    ):
            memo_content, summaries = await run_generate_plan(
                manifest_path=manifest_file,
                template_path=template_file,
                output_path=output_path,
                api_key="mock-key",
                provider="openai",
                model="gpt-4o",
                activation=True,
                context_dir=tmp_path,
            )

    assert memo_content is not None
    assert "Activation Memo" in memo_content
    assert "## Todo" in memo_content
    assert output_path.exists()
    assert "Activation Memo" in output_path.read_text()
