"""
Step for analyzing content with LLM.
"""

import json
import re
from typing import Any, Type

from loguru import logger
from pydantic import BaseModel

from skene.codebase import CodebaseExplorer
from skene.llm import LLMClient
from skene.output import status
from skene.strategies.context import AnalysisContext, StepResult
from skene.strategies.steps.base import AnalysisStep


class AnalyzeStep(AnalysisStep):
    """
    LLM analyzes content and produces structured output.

    This step takes file contents from context, asks the LLM to analyze them,
    and produces structured output (optionally validated against a Pydantic schema).

    Example:
        step = AnalyzeStep(
            prompt="Identify the tech stack from these configuration files",
            output_schema=TechStackSchema,
            output_key="tech_stack",
        )
    """

    name = "analyze"

    def __init__(
        self,
        prompt: str,
        output_key: str = "analysis",
        output_schema: Type[BaseModel] | None = None,
        source_key: str = "file_contents",
        include_request: bool = True,
    ):
        """
        Initialize the analysis step.

        Args:
            prompt: Instruction for the LLM on what to analyze
            output_key: Context key to store analysis result
            output_schema: Optional Pydantic model for structured output
            source_key: Context key containing file contents to analyze
            include_request: Whether to include original request in prompt
        """
        self.prompt = prompt
        self.output_key = output_key
        self.output_schema = output_schema
        self.source_key = source_key
        self.include_request = include_request

    async def execute(
        self,
        codebase: CodebaseExplorer,
        llm: LLMClient,
        context: AnalysisContext,
    ) -> StepResult:
        """Execute the analysis step."""
        try:
            # Get file contents from context
            file_contents = context.get(self.source_key, {})

            if not file_contents:
                logger.warning(f"AnalyzeStep: No file contents in context key '{self.source_key}'")

            # Build prompt for LLM
            llm_prompt = self._build_prompt(file_contents, context)

            # Get LLM response
            response = await llm.generate_content(llm_prompt)

            # Parse response
            parsed = self._parse_response(response)

            status(f"AnalyzeStep completed with {len(parsed)} keys in result")

            return StepResult(
                step_name=self.name,
                data={self.output_key: parsed},
                tokens_used=len(llm_prompt) // 4,  # Rough estimate
            )

        except Exception as e:
            logger.error(f"AnalyzeStep failed: {e}")
            return StepResult(
                step_name=self.name,
                error=str(e),
            )

    def _build_prompt(
        self,
        file_contents: dict[str, str],
        context: AnalysisContext,
    ) -> str:
        """Build the prompt for analysis."""
        prompt_parts = [
            "You are analyzing code files. Your task is to extract structured information.",
            "",
            "## Task",
            self.prompt,
        ]

        # Include original request if enabled
        if self.include_request and context.request:
            prompt_parts.extend(
                [
                    "",
                    "## Original Request",
                    context.request,
                ]
            )

        # Add file contents
        if file_contents:
            prompt_parts.extend(
                [
                    "",
                    "## Files to Analyze",
                ]
            )
            for path, content in file_contents.items():
                # Truncate very large files
                if len(content) > 50_000:
                    content = content[:50_000] + "\n... (truncated)"
                prompt_parts.extend(
                    [
                        "",
                        f"### {path}",
                        "```",
                        content,
                        "```",
                    ]
                )

        # Add output format instructions
        prompt_parts.extend(
            [
                "",
                "## Output Format",
            ]
        )

        if self.output_schema:
            # Generate schema description from Pydantic model
            schema = self.output_schema.model_json_schema()
            prompt_parts.extend(
                [
                    "Return your analysis as JSON matching this schema:",
                    "```json",
                    json.dumps(schema, indent=2),
                    "```",
                ]
            )
        else:
            prompt_parts.extend(
                [
                    "Return your analysis as a JSON object.",
                    "Include relevant keys based on your findings.",
                ]
            )

        prompt_parts.extend(
            [
                "",
                "Return ONLY valid JSON, no other text.",
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response to extract structured data."""

        def normalize_parsed(parsed: Any) -> dict[str, Any] | None:
            """Normalize parsed JSON to a dict, wrapping arrays if needed."""
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
            return None

        # Try direct JSON parse
        try:
            parsed = json.loads(response.strip())
            normalized = normalize_parsed(parsed)
            if normalized:
                return self._validate_output(normalized)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1).strip())
                normalized = normalize_parsed(parsed)
                if normalized:
                    return self._validate_output(normalized)
            except json.JSONDecodeError:
                pass

        # Try to find JSON object pattern
        obj_match = re.search(r"\{[\s\S]*\}", response)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group(0))
                normalized = normalize_parsed(parsed)
                if normalized:
                    return self._validate_output(normalized)
            except json.JSONDecodeError:
                pass

        # Try to find JSON array pattern
        arr_match = re.search(r"\[[\s\S]*\]", response)
        if arr_match:
            try:
                parsed = json.loads(arr_match.group(0))
                normalized = normalize_parsed(parsed)
                if normalized:
                    return self._validate_output(normalized)
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse analysis response as JSON: {response[:200]}")
        # Return raw response as fallback
        return {"raw_response": response}

    def _validate_output(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate output against schema if provided."""
        if self.output_schema:
            try:
                validated = self.output_schema.model_validate(data)
                return validated.model_dump()
            except Exception as e:
                logger.warning(f"Output validation failed: {e}")
                # Return unvalidated data
                return data
        return data
