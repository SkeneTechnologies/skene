"""
Step for generating final output with LLM.
"""

import json
import re
from datetime import datetime
from typing import Any, Type

from loguru import logger
from pydantic import BaseModel

from skene.codebase import CodebaseExplorer
from skene.llm import LLMClient
from skene.strategies.context import AnalysisContext, StepResult
from skene.strategies.steps.base import AnalysisStep


class GenerateStep(AnalysisStep):
    """
    LLM generates final output from accumulated context.

    This step is typically used as the final step in a strategy,
    combining all previous analysis into a final output.

    Example:
        step = GenerateStep(
            prompt="Combine the analysis into a complete growth manifest",
            output_schema=GrowthManifest,
        )
    """

    name = "generate"

    def __init__(
        self,
        prompt: str,
        output_schema: Type[BaseModel] | None = None,
        include_context_keys: list[str] | None = None,
        output_key: str = "output",
    ):
        """
        Initialize the generation step.

        Args:
            prompt: Instruction for the LLM on what to generate
            output_schema: Optional Pydantic model for structured output
            include_context_keys: Specific context keys to include (all if None)
            output_key: Context key to store generated output
        """
        self.prompt = prompt
        self.output_schema = output_schema
        self.include_context_keys = include_context_keys
        self.output_key = output_key

    async def execute(
        self,
        codebase: CodebaseExplorer,
        llm: LLMClient,
        context: AnalysisContext,
    ) -> StepResult:
        """Execute the generation step."""
        try:
            # Build prompt with context
            llm_prompt = self._build_prompt(context)

            # Get LLM response
            response = await llm.generate_content(llm_prompt)

            # Parse response
            parsed = self._parse_response(response, codebase)

            return StepResult(
                step_name=self.name,
                data={self.output_key: parsed},
                tokens_used=len(llm_prompt) // 4,  # Rough estimate
            )

        except Exception as e:
            logger.error(f"GenerateStep failed: {e}")
            return StepResult(
                step_name=self.name,
                error=str(e),
            )

    def _build_prompt(self, context: AnalysisContext) -> str:
        """Build the prompt for generation."""
        prompt_parts = [
            "You are generating structured output based on analysis results.",
            "",
            "## Task",
            self.prompt,
            "",
            "## Original Request",
            context.request,
        ]

        # Get context data to include
        all_data = context.get_all_data()
        if self.include_context_keys:
            data_to_include = {k: v for k, v in all_data.items() if k in self.include_context_keys}
        else:
            # Exclude large data like file_contents by default
            data_to_include = {k: v for k, v in all_data.items() if k != "file_contents" and not k.startswith("_")}

        if data_to_include:
            prompt_parts.extend(
                [
                    "",
                    "## Analysis Results",
                    "Use this information to generate your output:",
                    "",
                    "```json",
                    json.dumps(data_to_include, indent=2, default=str),
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
            schema = self.output_schema.model_json_schema()
            prompt_parts.extend(
                [
                    "Generate output as JSON matching this schema:",
                    "```json",
                    json.dumps(schema, indent=2),
                    "```",
                ]
            )
        else:
            prompt_parts.extend(
                [
                    "Generate output as a JSON object.",
                ]
            )

        prompt_parts.extend(
            [
                "",
                "Return ONLY valid JSON, no other text.",
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_response(self, response: str, codebase: CodebaseExplorer | None = None) -> dict[str, Any]:
        """Parse LLM response to extract structured data."""
        # Clean the response
        response = response.strip()

        # Try direct JSON parse
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                return self._validate_output(parsed, codebase)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block (with closing backticks)
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1).strip())
                if isinstance(parsed, dict):
                    return self._validate_output(parsed, codebase)
            except json.JSONDecodeError:
                pass

        # Try to extract JSON from incomplete markdown code block (without closing backticks)
        json_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)$", response)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1).strip())
                if isinstance(parsed, dict):
                    return self._validate_output(parsed, codebase)
            except json.JSONDecodeError:
                pass

        # Try to find JSON object pattern (greedy match for complete object)
        obj_match = re.search(r"\{[\s\S]*\}", response)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group(0))
                if isinstance(parsed, dict):
                    return self._validate_output(parsed, codebase)
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse generation response as JSON: {response[:200]}")
        return {"raw_response": response}

    def _unwrap_items(self, data: Any) -> Any:
        """Recursively unwrap JSON schema definitions and {'items': [...]} dicts back to plain lists."""
        if isinstance(data, dict):
            # Check if this is a JSON schema definition for an array
            # Pattern: {'type': 'array', 'items': [...]}
            if data.get("type") == "array" and "items" in data:
                items = data["items"]
                if isinstance(items, list):
                    # Direct list of items - unwrap each item recursively
                    return [self._unwrap_items(item) for item in items]
                # If items is a dict (schema definition), we can't extract data from it
                # Return empty list as fallback
                return []

            # If dict has only 'items' key with a list value, unwrap it
            if list(data.keys()) == ["items"] and isinstance(data["items"], list):
                return [self._unwrap_items(item) for item in data["items"]]

            # Otherwise recurse into dict values
            return {k: self._unwrap_items(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._unwrap_items(item) for item in data]
        return data

    def _validate_output(self, data: dict[str, Any], codebase: CodebaseExplorer | None = None) -> dict[str, Any]:
        """Validate output against schema if provided."""
        # Unwrap any {"items": [...]} patterns back to plain lists
        data = self._unwrap_items(data)

        if self.output_schema:
            try:
                # Ensure generated_at is set to current machine date for manifest schemas
                schema_name = self.output_schema.__name__
                if schema_name in ("GrowthManifest", "DocsManifest"):
                    # Always set generated_at to current machine date, overriding any LLM-provided value
                    # Remove it from data first so Pydantic uses the default_factory, then we'll set it explicitly
                    data.pop("generated_at", None)

                validated = self.output_schema.model_validate(data)

                # Explicitly set generated_at to current machine date after validation
                if schema_name in ("GrowthManifest", "DocsManifest"):
                    validated.generated_at = datetime.now()

                validated_dict = validated.model_dump()

                # Validate file paths exist if codebase is available
                if codebase:
                    validated_dict = self._validate_file_paths(validated_dict, codebase)

                return validated_dict
            except Exception as e:
                logger.warning(f"Output validation failed: {e}")
                return data
        return data

    def _validate_file_paths(self, data: dict[str, Any], codebase: CodebaseExplorer) -> dict[str, Any]:
        """Validate that all file_path fields in the manifest reference existing files."""

        # Validate current_growth_features
        if "current_growth_features" in data and isinstance(data["current_growth_features"], list):
            validated_features = []
            for feature in data["current_growth_features"]:
                if isinstance(feature, dict) and "file_path" in feature:
                    file_path = feature["file_path"]
                    full_path = codebase.base_dir / file_path
                    try:
                        # Check if file exists (synchronously for now, could be async if needed)
                        if full_path.exists() and full_path.is_file():
                            validated_features.append(feature)
                        else:
                            logger.warning(f"Removing feature with non-existent file_path: {file_path}")
                    except Exception as e:
                        logger.warning(f"Error validating file_path {file_path}: {e}")
                        # Keep the feature but log the warning
                        validated_features.append(feature)
                else:
                    validated_features.append(feature)
            data["current_growth_features"] = validated_features

        # Validate revenue_leakage file_paths
        if "revenue_leakage" in data and isinstance(data["revenue_leakage"], list):
            validated_leakage = []
            for leakage in data["revenue_leakage"]:
                if isinstance(leakage, dict) and "file_path" in leakage and leakage["file_path"]:
                    file_path = leakage["file_path"]
                    full_path = codebase.base_dir / file_path
                    try:
                        if full_path.exists() and full_path.is_file():
                            validated_leakage.append(leakage)
                        else:
                            logger.warning(f"Removing revenue_leakage with non-existent file_path: {file_path}")
                            # Remove file_path but keep the leakage entry
                            leakage_copy = leakage.copy()
                            leakage_copy["file_path"] = None
                            validated_leakage.append(leakage_copy)
                    except Exception as e:
                        logger.warning(f"Error validating file_path {file_path}: {e}")
                        validated_leakage.append(leakage)
                else:
                    validated_leakage.append(leakage)
            data["revenue_leakage"] = validated_leakage

        # Validate features (for DocsManifest)
        if "features" in data and isinstance(data["features"], list):
            validated_features = []
            for feature in data["features"]:
                if isinstance(feature, dict) and "file_path" in feature and feature["file_path"]:
                    file_path = feature["file_path"]
                    full_path = codebase.base_dir / file_path
                    try:
                        if full_path.exists() and full_path.is_file():
                            validated_features.append(feature)
                        else:
                            logger.warning(f"Removing feature with non-existent file_path: {file_path}")
                            # Remove file_path but keep the feature entry
                            feature_copy = feature.copy()
                            feature_copy["file_path"] = None
                            validated_features.append(feature_copy)
                    except Exception as e:
                        logger.warning(f"Error validating file_path {file_path}: {e}")
                        validated_features.append(feature)
                else:
                    validated_features.append(feature)
            data["features"] = validated_features

        return data
