"""
Multi-step analysis strategy.
"""

from skene.codebase import CodebaseExplorer
from skene.llm import LLMClient
from skene.output import debug, error, status
from skene.strategies.base import (
    AnalysisResult,
    AnalysisStrategy,
    ProgressCallback,
)
from skene.strategies.context import AnalysisContext
from skene.strategies.steps.base import AnalysisStep


class MultiStepStrategy(AnalysisStrategy):
    """
    Guided multi-step analysis strategy.

    Executes a predefined sequence of steps, where each step builds
    on the results of previous steps. This provides a predictable,
    deterministic analysis flow.

    Steps are defined as class attributes or passed to the constructor.
    Each step receives access to the codebase, LLM, and shared context.

    Example:
        class TechStackAnalyzer(MultiStepStrategy):
            steps = [
                SelectFilesStep(
                    prompt="Select configuration files",
                    patterns=["package.json", "*.config.*"],
                ),
                ReadFilesStep(),
                AnalyzeStep(
                    prompt="Identify the tech stack",
                    output_schema=TechStackSchema,
                ),
            ]

        analyzer = TechStackAnalyzer()
        result = await analyzer.run(codebase, llm, "Analyze this project")

    Alternative (pass steps to constructor):
        analyzer = MultiStepStrategy(steps=[
            SelectFilesStep(...),
            ReadFilesStep(),
            AnalyzeStep(...),
        ])
    """

    # Steps to execute - can be overridden by subclasses or passed to __init__
    steps: list[AnalysisStep] = []

    def __init__(self, steps: list[AnalysisStep] | None = None):
        """
        Initialize the multi-step strategy.

        Args:
            steps: Optional list of steps. If not provided, uses class attribute.
        """
        if steps is not None:
            self.steps = steps

    async def run(
        self,
        codebase: CodebaseExplorer,
        llm: LLMClient,
        request: str,
        on_progress: ProgressCallback | None = None,
        initial_context: dict | None = None,
    ) -> AnalysisResult:
        """
        Execute the multi-step analysis.

        Runs each step in sequence, passing the shared context between steps.
        Progress is reported after each step completes.

        Args:
            codebase: Access to the codebase files
            llm: LLM client for generation
            request: User's analysis request
            on_progress: Optional callback for progress updates
            initial_context: Optional initial data to seed the context with

        Returns:
            AnalysisResult with combined data from all steps
        """
        # Initialize context
        context = AnalysisContext(request=request)
        context.metadata.total_steps = len(self.steps)

        # Seed context with initial data if provided
        if initial_context:
            for key, value in initial_context.items():
                context.set(key, value)
        context.metadata.model_name = llm.get_model_name()
        context.metadata.provider_name = llm.get_provider_name()

        total_steps = len(self.steps)

        if total_steps == 0:
            from loguru import logger

            logger.warning("MultiStepStrategy has no steps defined")
            return AnalysisResult.error_result(
                error="No steps defined in strategy",
                metadata=context.metadata,
            )

        status(f"Starting MultiStepStrategy with {total_steps} steps")

        # Execute each step
        for i, step in enumerate(self.steps):
            step_num = i + 1
            step_name = step.name

            # Report progress
            if on_progress:
                progress = (i / total_steps) * 100
                on_progress(f"Step {step_num}/{total_steps}: {step_name}", progress)

            status(f"Executing step {step_num}/{total_steps}: {step_name}")

            try:
                # Execute the step
                result = await step.execute(codebase, llm, context)

                # Add result to context
                context.add_step_result(step_name, result)

                # Check for errors
                if not result.success:
                    error(f"Step {step_name} failed: {result.error}")
                    if on_progress:
                        on_progress(f"Failed at step {step_name}", -1)
                    return AnalysisResult.error_result(
                        error=f"Step '{step_name}' failed: {result.error}",
                        metadata=context.metadata,
                    )

                debug(f"Step {step_name} completed successfully")

            except Exception as e:
                error(f"Step {step_name} raised exception: {e}")
                if on_progress:
                    on_progress(f"Error in step {step_name}", -1)
                return AnalysisResult.error_result(
                    error=f"Step '{step_name}' raised exception: {str(e)}",
                    metadata=context.metadata,
                )

        # All steps completed
        if on_progress:
            on_progress("Complete", 100.0)

        status(
            f"MultiStepStrategy completed successfully. "
            f"Files read: {len(context.metadata.files_read)}, "
            f"Tokens used: {context.metadata.tokens_used}"
        )

        return context.to_result()
