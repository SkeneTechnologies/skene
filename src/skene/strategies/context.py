"""
Analysis context for sharing state between steps.
"""

from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from skene.strategies.base import AnalysisMetadata, AnalysisResult


class StepResult(BaseModel):
    """Result from a single analysis step."""

    step_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    files_read: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        """Whether the step succeeded."""
        return self.error is None


class AnalysisContext(BaseModel):
    """
    Shared context passed between analysis steps.

    Accumulates results from each step and provides a unified view
    of the analysis state. Steps can read from previous results
    and add their own data.

    Example:
        context = AnalysisContext(request="Analyze this repo")

        # After step 1
        context.add_step_result("select_files", StepResult(
            step_name="select_files",
            data={"selected_files": ["src/main.py", "src/utils.py"]}
        ))

        # In step 2, access previous results
        files = context.get("selected_files", [])
    """

    request: str
    step_results: list[StepResult] = Field(default_factory=list)
    metadata: AnalysisMetadata = Field(default_factory=AnalysisMetadata)

    # Accumulated data from all steps (merged) - private attribute
    _accumulated_data: dict[str, Any] = PrivateAttr(default_factory=dict)

    def add_step_result(self, step_name: str, result: StepResult) -> None:
        """
        Add a step result to the context.

        The step's data is merged into accumulated_data for easy access.
        Files read and tokens used are tracked in metadata.

        Args:
            step_name: Name of the step
            result: The step's result
        """
        self.step_results.append(result)
        self.metadata.steps_completed += 1

        # Merge step data into accumulated data
        self._accumulated_data.update(result.data)

        # Track files and tokens
        self.metadata.files_read.extend(result.files_read)
        self.metadata.tokens_used += result.tokens_used

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from accumulated data.

        This provides easy access to data from any previous step.

        Args:
            key: The key to look up
            default: Default value if key not found

        Returns:
            The value, or default if not found
        """
        return self._accumulated_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in accumulated data.

        Useful for steps that need to modify or add data outside
        of the normal step result flow.

        Args:
            key: The key to set
            value: The value to store
        """
        self._accumulated_data[key] = value

    def get_all_data(self) -> dict[str, Any]:
        """Get all accumulated data from all steps."""
        return dict(self._accumulated_data)

    def get_step_result(self, step_name: str) -> StepResult | None:
        """Get the result of a specific step by name."""
        for result in self.step_results:
            if result.step_name == step_name:
                return result
        return None

    def to_result(self) -> AnalysisResult:
        """
        Convert context to final AnalysisResult.

        Call this at the end of a strategy to get the final result.

        Returns:
            AnalysisResult with all accumulated data
        """
        # Check if any step failed
        for step_result in self.step_results:
            if not step_result.success:
                return AnalysisResult.error_result(
                    error=f"Step '{step_result.step_name}' failed: {step_result.error}",
                    metadata=self.metadata,
                )

        return AnalysisResult.success_result(
            data=self.get_all_data(),
            metadata=self.metadata,
        )
