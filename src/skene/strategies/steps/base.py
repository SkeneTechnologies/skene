"""
Base class for analysis steps.
"""

from abc import ABC, abstractmethod

from skene.codebase import CodebaseExplorer
from skene.llm import LLMClient
from skene.strategies.context import AnalysisContext, StepResult


class AnalysisStep(ABC):
    """
    Abstract base class for analysis steps.

    Each step performs a specific operation in the analysis pipeline.
    Steps receive the codebase, LLM client, and shared context,
    and return a StepResult with their output.

    Example:
        class MyStep(AnalysisStep):
            name = "my_step"

            async def execute(self, codebase, llm, context):
                # Do something
                return StepResult(
                    step_name=self.name,
                    data={"result": "value"}
                )
    """

    # Step name - should be overridden by subclasses
    name: str = "base_step"

    @abstractmethod
    async def execute(
        self,
        codebase: CodebaseExplorer,
        llm: LLMClient,
        context: AnalysisContext,
    ) -> StepResult:
        """
        Execute this analysis step.

        Args:
            codebase: Access to the codebase files
            llm: LLM client for generation
            context: Shared context with accumulated data from previous steps

        Returns:
            StepResult with step output and metadata
        """
        pass
