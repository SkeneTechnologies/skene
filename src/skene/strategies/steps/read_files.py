"""
Step for reading files into context.
"""

from loguru import logger
from rich.console import Console

from skene.codebase import CodebaseExplorer
from skene.llm import LLMClient
from skene.strategies.context import AnalysisContext, StepResult
from skene.strategies.steps.base import AnalysisStep

console = Console()


class ReadFilesStep(AnalysisStep):
    """
    Read files selected in a previous step.

    This step reads files from the codebase and stores their contents
    in the context for subsequent steps to use.

    Example:
        step = ReadFilesStep(
            source_key="selected_files",  # Key from previous SelectFilesStep
            output_key="file_contents",
        )
    """

    name = "read_files"

    def __init__(
        self,
        source_key: str = "selected_files",
        output_key: str = "file_contents",
        max_file_size: int = 100_000,  # 100KB max per file
    ):
        """
        Initialize the file reading step.

        Args:
            source_key: Context key containing list of files to read
            output_key: Context key to store file contents
            max_file_size: Maximum file size in bytes to read (skip larger files)
        """
        self.source_key = source_key
        self.output_key = output_key
        self.max_file_size = max_file_size

    async def execute(
        self,
        codebase: CodebaseExplorer,
        llm: LLMClient,
        context: AnalysisContext,
    ) -> StepResult:
        """Execute the file reading step."""
        try:
            # Get files to read from context
            files_to_read = context.get(self.source_key, [])

            if not files_to_read:
                logger.warning(f"ReadFilesStep: No files found in context key '{self.source_key}'")
                return StepResult(
                    step_name=self.name,
                    data={self.output_key: {}},
                    files_read=[],
                )

            # Read all files
            file_contents: dict[str, str] = {}
            files_read: list[str] = []
            skipped_files: list[str] = []

            for file_path in files_to_read:
                # Check file size first
                info_result = await codebase.get_file_info(file_path)
                if "error" in info_result:
                    console.print(f"Skipping {file_path}: {info_result['error']}")
                    skipped_files.append(file_path)
                    continue

                if info_result.get("size", 0) > self.max_file_size:
                    console.print(f"Skipping {file_path}: too large ({info_result['size']} > {self.max_file_size})")
                    skipped_files.append(file_path)
                    continue

                # Read the file
                read_result = await codebase.read_file(file_path)
                if "error" in read_result:
                    console.print(f"Failed to read {file_path}: {read_result['error']}")
                    skipped_files.append(file_path)
                    continue

                file_contents[file_path] = read_result["content"]
                files_read.append(file_path)

            console.print(f"ReadFilesStep read {len(files_read)} files, skipped {len(skipped_files)}")

            return StepResult(
                step_name=self.name,
                data={
                    self.output_key: file_contents,
                    "files_read_count": len(files_read),
                    "files_skipped": skipped_files,
                },
                files_read=files_read,
            )

        except Exception as e:
            logger.error(f"ReadFilesStep failed: {e}")
            return StepResult(
                step_name=self.name,
                error=str(e),
            )
