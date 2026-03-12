"""
Step for selecting relevant files using LLM.
"""

import json
import re

from loguru import logger
from rich.console import Console

from skene.codebase import CodebaseExplorer
from skene.llm import LLMClient
from skene.strategies.context import AnalysisContext, StepResult
from skene.strategies.steps.base import AnalysisStep

console = Console()


class SelectFilesStep(AnalysisStep):
    """
    LLM selects relevant files based on criteria.

    This step asks the LLM to analyze the directory structure and
    select files that are most relevant for the analysis task.

    Example:
        step = SelectFilesStep(
            prompt="Select files that reveal the project's tech stack",
            patterns=["package.json", "*.config.*", "src/**/*.ts"],
            max_files=20,
        )
    """

    name = "select_files"

    def __init__(
        self,
        prompt: str,
        patterns: list[str] | None = None,
        max_files: int = 20,
        output_key: str = "selected_files",
    ):
        """
        Initialize the file selection step.

        Args:
            prompt: Instruction for the LLM on what files to select
            patterns: Optional glob patterns to pre-filter candidates
            max_files: Maximum number of files to select
            output_key: Key to store selected files in context
        """
        self.prompt = prompt
        self.patterns = patterns
        self.max_files = max_files
        self.output_key = output_key

    async def execute(
        self,
        codebase: CodebaseExplorer,
        llm: LLMClient,
        context: AnalysisContext,
    ) -> StepResult:
        """Execute the file selection step."""
        try:
            # Get directory tree for context
            tree_result = await codebase.get_directory_tree(".", max_depth=4)
            if "error" in tree_result:
                return StepResult(
                    step_name=self.name,
                    error=f"Failed to get directory tree: {tree_result['error']}",
                )

            tree = tree_result["tree"]

            # If patterns provided, get candidate files
            candidates: list[str] = []
            if self.patterns:
                for pattern in self.patterns:
                    search_result = await codebase.search_files(".", pattern)
                    if "matches" in search_result:
                        for match in search_result["matches"]:
                            if match["type"] == "file":
                                candidates.append(match["path"])
                candidates = list(set(candidates))  # Dedupe

            # Build prompt for LLM
            llm_prompt = self._build_prompt(tree, candidates, context)

            # Ask LLM to select files
            response = await llm.generate_content(llm_prompt)

            # Parse response to get file list
            selected_files = self._parse_response(response)

            # Filter out excluded files
            selected_files = self._filter_excluded_files(codebase, selected_files)

            # Limit to max_files
            selected_files = selected_files[: self.max_files]

            console.print(f"SelectFilesStep selected {len(selected_files)} files")

            return StepResult(
                step_name=self.name,
                data={self.output_key: selected_files},
                tokens_used=len(llm_prompt) // 4,  # Rough estimate
            )

        except Exception as e:
            logger.error(f"SelectFilesStep failed: {e}")
            return StepResult(
                step_name=self.name,
                error=str(e),
            )

    def _build_prompt(
        self,
        tree: str,
        candidates: list[str],
        context: AnalysisContext,
    ) -> str:
        """Build the prompt for file selection."""
        prompt_parts = [
            "You are analyzing a codebase. Your task is to select the most relevant files.",
            "",
            "## Task",
            self.prompt,
            "",
            "## Directory Structure",
            "```",
            tree,
            "```",
        ]

        if candidates:
            prompt_parts.extend(
                [
                    "",
                    "## Candidate Files (matching patterns)",
                    "These files match the search patterns and may be particularly relevant:",
                    "",
                ]
            )
            for f in candidates[:50]:  # Limit candidates shown
                prompt_parts.append(f"- {f}")

        # Include context from previous steps if available
        if context.get("request"):
            prompt_parts.extend(
                [
                    "",
                    "## Original Request",
                    context.request,
                ]
            )

        prompt_parts.extend(
            [
                "",
                "## Instructions",
                f"Select up to {self.max_files} files that are most relevant for this task.",
                "Return ONLY a JSON array of file paths, nothing else.",
                "",
                "Example response:",
                '["src/main.ts", "package.json", "src/config.ts"]',
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_response(self, response: str) -> list[str]:
        """Parse LLM response to extract file list."""
        # Try to find JSON array in response
        # First, try direct JSON parse
        try:
            files = json.loads(response.strip())
            if isinstance(files, list):
                return [f for f in files if isinstance(f, str)]
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response)
        if json_match:
            try:
                files = json.loads(json_match.group(1).strip())
                if isinstance(files, list):
                    return [f for f in files if isinstance(f, str)]
            except json.JSONDecodeError:
                pass

        # Try to extract array pattern
        array_match = re.search(r"\[[\s\S]*?\]", response)
        if array_match:
            try:
                files = json.loads(array_match.group(0))
                if isinstance(files, list):
                    return [f for f in files if isinstance(f, str)]
            except json.JSONDecodeError:
                pass

        # Fallback: extract quoted strings that look like paths
        path_pattern = r'"([^"]+\.[a-zA-Z]+)"'
        matches = re.findall(path_pattern, response)
        if matches:
            return matches

        logger.warning(f"Could not parse file selection response: {response[:200]}")
        return []

    def _filter_excluded_files(self, codebase: CodebaseExplorer, file_paths: list[str]) -> list[str]:
        """Filter out files that match exclusion criteria."""
        filtered = []
        for file_path in file_paths:
            # Resolve the file path relative to codebase base_dir
            try:
                # Create a Path object relative to base_dir
                full_path = codebase.base_dir / file_path
                # Check if this path should be excluded
                if not codebase.should_exclude(full_path):
                    filtered.append(file_path)
                else:
                    console.print(f"Excluding file: {file_path}")
            except Exception as e:
                # If path resolution fails, log and skip
                logger.warning(f"Could not check exclusion for {file_path}: {e}")
                # Include it by default to avoid breaking the analysis
                filtered.append(file_path)
        return filtered
