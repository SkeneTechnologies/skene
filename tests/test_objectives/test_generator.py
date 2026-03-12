"""Tests for objectives generator module."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from skene.llm.base import LLMClient
from skene.objectives.generator import (
    _format_markdown,
    _parse_json_response,
    _validate_objectives,
    generate_objectives,
    write_objectives_output,
)


class FakeLLM(LLMClient):
    """Fake LLM client for testing."""

    def __init__(self, response: str):
        self.response = response
        self.last_prompt: str | None = None

    async def generate_content(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response

    async def generate_content_stream(self, prompt: str):
        self.last_prompt = prompt
        yield self.response

    def get_model_name(self) -> str:
        return "fake-model"

    def get_provider_name(self) -> str:
        return "fake-provider"


def _build_sample_objectives() -> list[dict]:
    """Build sample objectives for testing."""
    return [
        {
            "lifecycle": "ACQUISITION",
            "metric": "Website Conversion Rate",
            "target": "> 2.5%",
            "tolerance": "+/- 0.5% (2.0-3.0%)",
        },
        {
            "lifecycle": "ACTIVATION",
            "metric": "Time to Value",
            "target": "< 10 minutes",
            "tolerance": "+/- 20% (8-12 minutes)",
        },
        {
            "lifecycle": "RETENTION",
            "metric": "30-Day Retention",
            "target": "> 25%",
            "tolerance": "+/- 3% (22-28%)",
        },
    ]


def _build_sample_manifest() -> dict:
    """Build sample manifest for testing."""
    return {
        "version": "1.0",
        "project_name": "Test Project",
        "tech_stack": {
            "language": "TypeScript",
            "framework": "Next.js",
        },
        "growth_hubs": [
            {"name": "User Auth", "description": "Authentication features"},
        ],
        "gtm_gaps": [
            {"name": "Referral System", "description": "Missing referrals", "priority": "high"},
        ],
    }


def _build_sample_template() -> dict:
    """Build sample template for testing."""
    return {
        "title": "Test PLG Template",
        "lifecycles": [
            {
                "name": "ACQUISITION",
                "metrics": [
                    {"name": "Conversion Rate", "howToMeasure": "% visitors who sign up", "healthyBenchmark": "> 2.5%"},
                ],
            },
            {
                "name": "ACTIVATION",
                "metrics": [
                    {"name": "Time to Value", "howToMeasure": "Time to first action", "healthyBenchmark": "< 10 min"},
                ],
            },
        ],
    }


class TestParseJsonResponse:
    """Tests for _parse_json_response function."""

    def test_parse_raw_json_array(self):
        """Test parsing raw JSON array."""
        objectives = _build_sample_objectives()
        response = json.dumps(objectives)

        result = _parse_json_response(response)

        assert len(result) == 3
        assert result[0]["lifecycle"] == "ACQUISITION"

    def test_parse_json_from_codefence(self):
        """Test parsing JSON from markdown code fence."""
        objectives = _build_sample_objectives()
        response = f"```json\n{json.dumps(objectives, indent=2)}\n```"

        result = _parse_json_response(response)

        assert len(result) == 3
        assert result[1]["lifecycle"] == "ACTIVATION"

    def test_parse_json_from_codefence_no_language(self):
        """Test parsing JSON from code fence without language tag."""
        objectives = _build_sample_objectives()
        response = f"```\n{json.dumps(objectives)}\n```"

        result = _parse_json_response(response)

        assert len(result) == 3

    def test_parse_json_embedded_in_text(self):
        """Test parsing JSON array embedded in text."""
        objectives = _build_sample_objectives()
        response = f"Here are the objectives:\n{json.dumps(objectives)}\nThese are good."

        result = _parse_json_response(response)

        assert len(result) == 3

    def test_parse_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_json_response("This is not JSON at all")


class TestValidateObjectives:
    """Tests for _validate_objectives function."""

    def test_validate_valid_objectives(self):
        """Test validation passes for valid objectives."""
        objectives = _build_sample_objectives()
        # Should not raise
        _validate_objectives(objectives)

    def test_validate_missing_field_raises_error(self):
        """Test validation fails when required field is missing."""
        objectives = [
            {"lifecycle": "ACQUISITION", "metric": "Rate"},  # missing target and tolerance
        ]

        with pytest.raises(ValueError, match="missing required fields"):
            _validate_objectives(objectives)

    def test_validate_does_not_raise_on_wrong_count(self):
        """Test validation does not raise error when not exactly 3 objectives (just warns)."""
        objectives = _build_sample_objectives()[:2]  # Only 2

        # Should not raise - just logs a warning
        _validate_objectives(objectives)


class TestFormatMarkdown:
    """Tests for _format_markdown function."""

    def test_format_markdown_basic(self):
        """Test basic markdown formatting."""
        objectives = _build_sample_objectives()

        result = _format_markdown(objectives)

        assert "# Growth Objectives" in result
        assert "## ACQUISITION" in result
        assert "## ACTIVATION" in result
        assert "## RETENTION" in result
        assert "**Metric:** Website Conversion Rate" in result
        assert "**Target:** > 2.5%" in result
        assert "**Tolerance:** +/- 0.5% (2.0-3.0%)" in result

    def test_format_markdown_with_quarter(self):
        """Test markdown formatting with quarter label."""
        objectives = _build_sample_objectives()

        result = _format_markdown(objectives, quarter="Q1 2024")

        assert "# Growth Objectives Q1 2024" in result

    def test_format_markdown_includes_generated_date(self):
        """Test that markdown includes generated date."""
        objectives = _build_sample_objectives()

        result = _format_markdown(objectives)

        assert "*Generated on" in result

    def test_format_markdown_date_is_system_date(self):
        """Test that the generated date is the actual system date."""
        objectives = _build_sample_objectives()
        expected_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = _format_markdown(objectives)

        assert f"*Generated on {expected_date}*" in result

    def test_format_markdown_date_uses_frozen_time(self):
        """Test that date comes from system, not LLM."""
        objectives = _build_sample_objectives()

        # Mock datetime to verify it's using system time
        with patch("skene.objectives.generator.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2099-12-31 23:59:59"
            result = _format_markdown(objectives)

        assert "*Generated on 2099-12-31 23:59:59*" in result
        mock_datetime.now.assert_called_once()

    def test_format_markdown_includes_footer(self):
        """Test that markdown includes footer."""
        objectives = _build_sample_objectives()

        result = _format_markdown(objectives)

        assert "Growth objectives generated by skene" in result


class TestGenerateObjectives:
    """Tests for generate_objectives async function."""

    @pytest.mark.asyncio
    async def test_generate_objectives_success(self):
        """Test successful objectives generation."""
        objectives = _build_sample_objectives()
        llm = FakeLLM(json.dumps(objectives))
        manifest = _build_sample_manifest()
        template = _build_sample_template()

        result = await generate_objectives(llm, manifest, template)

        assert "# Growth Objectives" in result
        assert "## ACQUISITION" in result
        assert "**Metric:** Website Conversion Rate" in result

    @pytest.mark.asyncio
    async def test_generate_objectives_with_quarter(self):
        """Test objectives generation with quarter label."""
        objectives = _build_sample_objectives()
        llm = FakeLLM(json.dumps(objectives))
        manifest = _build_sample_manifest()
        template = _build_sample_template()

        result = await generate_objectives(llm, manifest, template, quarter="Q2")

        assert "# Growth Objectives Q2" in result

    @pytest.mark.asyncio
    async def test_generate_objectives_prompt_includes_manifest(self):
        """Test that prompt includes manifest data."""
        objectives = _build_sample_objectives()
        llm = FakeLLM(json.dumps(objectives))
        manifest = _build_sample_manifest()
        template = _build_sample_template()

        await generate_objectives(llm, manifest, template)

        assert llm.last_prompt is not None
        assert "Test Project" in llm.last_prompt
        assert "gtm_gaps" in llm.last_prompt or "Referral System" in llm.last_prompt

    @pytest.mark.asyncio
    async def test_generate_objectives_prompt_includes_template(self):
        """Test that prompt includes template data."""
        objectives = _build_sample_objectives()
        llm = FakeLLM(json.dumps(objectives))
        manifest = _build_sample_manifest()
        template = _build_sample_template()

        await generate_objectives(llm, manifest, template)

        assert llm.last_prompt is not None
        assert "ACQUISITION" in llm.last_prompt
        assert "lifecycles" in llm.last_prompt

    @pytest.mark.asyncio
    async def test_generate_objectives_with_guidance(self):
        """Test objectives generation with guidance text."""
        objectives = _build_sample_objectives()
        llm = FakeLLM(json.dumps(objectives))
        manifest = _build_sample_manifest()
        template = _build_sample_template()

        result = await generate_objectives(llm, manifest, template, guidance="Focus on onboarding")

        assert "# Growth Objectives" in result

    @pytest.mark.asyncio
    async def test_generate_objectives_prompt_includes_guidance(self):
        """Test that prompt includes guidance when provided."""
        objectives = _build_sample_objectives()
        llm = FakeLLM(json.dumps(objectives))
        manifest = _build_sample_manifest()
        template = _build_sample_template()
        guidance = "I want all objectives to focus on onboarding"

        await generate_objectives(llm, manifest, template, guidance=guidance)

        assert llm.last_prompt is not None
        assert "User Guidance" in llm.last_prompt
        assert guidance in llm.last_prompt
        assert "onboarding" in llm.last_prompt.lower()

    @pytest.mark.asyncio
    async def test_generate_objectives_prompt_without_guidance(self):
        """Test that prompt doesn't include guidance section when not provided."""
        objectives = _build_sample_objectives()
        llm = FakeLLM(json.dumps(objectives))
        manifest = _build_sample_manifest()
        template = _build_sample_template()

        await generate_objectives(llm, manifest, template)

        assert llm.last_prompt is not None
        assert "User Guidance" not in llm.last_prompt


class TestWriteObjectivesOutput:
    """Tests for write_objectives_output function."""

    def test_write_objectives_output(self, tmp_path):
        """Test writing objectives markdown to file."""
        markdown_content = "# Growth Objectives\n\n## Test\n- **Metric:** Test"
        output_path = tmp_path / "growth-objectives.md"

        result = write_objectives_output(markdown_content, output_path)

        assert result.exists()
        assert result.read_text() == markdown_content

    def test_write_objectives_output_creates_parent_dirs(self, tmp_path):
        """Test that parent directories are created if they don't exist."""
        markdown_content = "# Test"
        output_path = tmp_path / "nested" / "dir" / "objectives.md"

        result = write_objectives_output(markdown_content, output_path)

        assert result.exists()
        assert result.read_text() == markdown_content

    def test_write_objectives_output_returns_path(self, tmp_path):
        """Test that function returns the output path."""
        markdown_content = "# Test"
        output_path = tmp_path / "objectives.md"

        result = write_objectives_output(markdown_content, output_path)

        assert result == output_path
