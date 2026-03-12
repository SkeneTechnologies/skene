import json

import pytest

from skene.llm.base import LLMClient
from skene.templates.growth_template import (
    generate_growth_template,
    load_example_templates,
    write_growth_template_outputs,
)


class FakeLLM(LLMClient):
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


def _build_candidate_template() -> dict:
    """Build a sample PLG lifecycle template for testing."""
    return {
        "title": "Test SaaS PLG Template",
        "description": "Product-led growth template for testing purposes",
        "version": "1.0.0",
        "framework": "Test-PLG",
        "lifecycles": [
            {
                "name": "ACQUISITION",
                "description": "The Hook",
                "order_index": 1,
                "milestones": [
                    {
                        "title": "Website Visit",
                        "description": "User lands on website",
                        "order_index": 1,
                    },
                    {"title": "Sign Up", "description": "User creates account", "order_index": 2},
                ],
                "metrics": [
                    {
                        "name": "Conversion Rate",
                        "howToMeasure": "% of visitors who sign up",
                        "healthyBenchmark": "> 2.5%",
                    },
                    {
                        "name": "Time to Sign-Up",
                        "howToMeasure": "Average time from landing to account creation",
                        "healthyBenchmark": "< 5 minutes",
                    },
                    {
                        "name": "Traffic Quality",
                        "howToMeasure": "Conversion rate by source",
                        "healthyBenchmark": "> 3%",
                    },
                ],
            },
            {
                "name": "ACTIVATION",
                "description": "First Value",
                "order_index": 2,
                "milestones": [
                    {
                        "title": "Onboarding Start",
                        "description": "User begins onboarding flow",
                        "order_index": 1,
                    },
                    {
                        "title": "First Action",
                        "description": "User completes primary action",
                        "order_index": 2,
                    },
                    {
                        "title": "Aha Moment",
                        "description": "User experiences core value",
                        "order_index": 3,
                    },
                ],
                "metrics": [
                    {
                        "name": "Activation Rate",
                        "howToMeasure": "% of users reaching aha moment in 7 days",
                        "healthyBenchmark": "> 40%",
                    },
                    {
                        "name": "Time to Value",
                        "howToMeasure": "Average time to first core action",
                        "healthyBenchmark": "< 10 minutes",
                    },
                    {
                        "name": "Day-1 Retention",
                        "howToMeasure": "% returning within 24 hours",
                        "healthyBenchmark": "> 50%",
                    },
                ],
            },
            {
                "name": "RETENTION",
                "description": "Sticky Value",
                "order_index": 3,
                "milestones": [
                    {
                        "title": "Week 2 Return",
                        "description": "User active after 2 weeks",
                        "order_index": 1,
                    },
                    {
                        "title": "Regular Usage",
                        "description": "User establishes usage pattern",
                        "order_index": 2,
                    },
                ],
                "metrics": [
                    {
                        "name": "30-Day Retention",
                        "howToMeasure": "% active after 30 days",
                        "healthyBenchmark": "> 25%",
                    },
                    {
                        "name": "Churn Rate",
                        "howToMeasure": "% stopping usage per month",
                        "healthyBenchmark": "< 5%",
                    },
                    {
                        "name": "Weekly Active Users",
                        "howToMeasure": "% engaging weekly",
                        "healthyBenchmark": "> 30%",
                    },
                ],
            },
        ],
        "metadata": {
            "framework_description": "Test PLG framework for unit testing",
            "usage": "Use for testing growth template generation",
            "created_at": "2026-01-15",
            "category": "Test",
        },
    }


def test_load_example_templates():
    """Test loading example templates from the templates directory."""
    examples = load_example_templates()
    assert isinstance(examples, list)
    # Should have at least the PLG and design-agency templates
    assert len(examples) >= 1


@pytest.mark.asyncio
async def test_generate_growth_template_parses_json():
    """Test that LLM response is parsed correctly from raw JSON."""
    candidate = _build_candidate_template()
    llm = FakeLLM(json.dumps(candidate))

    generated = await generate_growth_template(llm, {"project_name": "Test Project"})

    assert generated["title"] == "Test SaaS PLG Template"
    assert "lifecycles" in generated
    assert len(generated["lifecycles"]) == 3
    # Verify metrics are present
    for lifecycle in generated["lifecycles"]:
        assert "metrics" in lifecycle
        assert len(lifecycle["metrics"]) >= 3


@pytest.mark.asyncio
async def test_generate_growth_template_parses_codefence_json():
    """Test that LLM response is parsed correctly from markdown code fence."""
    candidate = _build_candidate_template()
    response = f"```json\n{json.dumps(candidate, indent=2)}\n```"
    llm = FakeLLM(response)

    generated = await generate_growth_template(llm, {"project_name": "Test Project"})

    assert generated["description"] == "Product-led growth template for testing purposes"
    assert len(generated["lifecycles"]) == 3
    # Verify all lifecycles have metrics
    for lifecycle in generated["lifecycles"]:
        assert "metrics" in lifecycle


@pytest.mark.asyncio
async def test_generate_growth_template_with_business_type():
    """Test that business type is passed to prompt generation."""
    candidate = _build_candidate_template()
    llm = FakeLLM(json.dumps(candidate))

    generated = await generate_growth_template(llm, {"project_name": "Design Studio"}, business_type="design-agency")

    # Verify template was generated successfully
    assert generated["title"] == "Test SaaS PLG Template"
    # Verify prompt includes business type context
    assert llm.last_prompt is not None
    assert "design-agency" in llm.last_prompt or "Business type" in llm.last_prompt


def test_write_growth_template_outputs(tmp_path):
    """Test writing template outputs to JSON file."""
    candidate = _build_candidate_template()

    json_path = write_growth_template_outputs(candidate, tmp_path)

    assert json_path.exists()
    assert json.loads(json_path.read_text())["title"] == "Test SaaS PLG Template"
