"""
Base classes for analysis strategies.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel, Field

from skene.codebase import CodebaseExplorer
from skene.llm import LLMClient

# Type alias for progress callbacks
# Callback receives (message: str, percentage: float)
# percentage is 0-100, or -1 for indeterminate progress
ProgressCallback = Callable[[str, float], None]


class AnalysisMetadata(BaseModel):
    """Metadata about an analysis run."""

    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    total_steps: int = 0
    steps_completed: int = 0
    files_read: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    model_name: str | None = None
    provider_name: str | None = None

    def mark_complete(self) -> None:
        """Mark the analysis as complete."""
        self.completed_at = datetime.now()

    @property
    def duration_ms(self) -> int | None:
        """Get duration in milliseconds, or None if not complete."""
        if self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)


class AnalysisResult(BaseModel):
    """Result from any analysis strategy."""

    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    metadata: AnalysisMetadata = Field(default_factory=AnalysisMetadata)

    @classmethod
    def success_result(
        cls,
        data: dict[str, Any],
        metadata: AnalysisMetadata | None = None,
    ) -> "AnalysisResult":
        """Create a successful result."""
        meta = metadata or AnalysisMetadata()
        meta.mark_complete()
        return cls(success=True, data=data, metadata=meta)

    @classmethod
    def error_result(
        cls,
        error: str,
        metadata: AnalysisMetadata | None = None,
    ) -> "AnalysisResult":
        """Create an error result."""
        meta = metadata or AnalysisMetadata()
        meta.mark_complete()
        return cls(success=False, error=error, metadata=meta)


class AnalysisStrategy(ABC):
    """
    Abstract base class for all analysis strategies.

    Strategies define how an analysis is conducted - e.g. through
    a predefined sequence of steps (MultiStepStrategy).

    Example:
        class MyStrategy(AnalysisStrategy):
            async def run(self, codebase, llm, request, on_progress=None):
                # Implementation here
                return AnalysisResult.success_result({"key": "value"})

        strategy = MyStrategy()
        result = await strategy.run(codebase, llm, "Analyze this repo")
    """

    @abstractmethod
    async def run(
        self,
        codebase: CodebaseExplorer,
        llm: LLMClient,
        request: str,
        on_progress: ProgressCallback | None = None,
    ) -> AnalysisResult:
        """
        Execute the analysis strategy.

        Args:
            codebase: Access to the codebase files
            llm: LLM client for generation
            request: User's analysis request/prompt
            on_progress: Optional callback for progress updates.
                        Called with (message, percentage) where percentage
                        is 0-100 or -1 for indeterminate.

        Returns:
            AnalysisResult with success status, data, and metadata
        """
        pass
