"""
Codebase exploration tools for safe, sandboxed file system access.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

from skene.codebase.filters import DEFAULT_EXCLUDE_FOLDERS


class CodebaseExplorer:
    """
    Safe, sandboxed access to a codebase.

    Provides file system tools that work within a sandboxed base directory.
    All paths are resolved relative to the base directory, with security
    checks to prevent path traversal attacks.

    Example:
        explorer = CodebaseExplorer("/path/to/repo")
        tree = await explorer.get_directory_tree(".")
        content = await explorer.read_file("src/main.py")
    """

    def __init__(
        self,
        base_dir: Path | str,
        exclude_folders: list[str] | None = None,
    ):
        """
        Initialize the codebase explorer.

        Args:
            base_dir: Base directory to explore (all paths are relative to this)
            exclude_folders: Folder names to exclude from exploration.
                           Defaults to DEFAULT_EXCLUDE_FOLDERS if not specified.
        """
        self.base_dir = Path(base_dir).resolve()
        self.exclude_folders = set(exclude_folders if exclude_folders is not None else DEFAULT_EXCLUDE_FOLDERS)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """
        Convert relative path to absolute, ensuring it stays within base_dir.

        Args:
            relative_path: Path relative to base_dir

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If the resolved path is outside base_dir
        """
        clean_path = relative_path.lstrip("/")
        full_path = (self.base_dir / clean_path).resolve()

        # Security check: ensure path is within base_dir
        if not str(full_path).startswith(str(self.base_dir)):
            raise ValueError("Access denied: Path is outside allowed directory")

        return full_path

    def should_exclude(self, path: Path) -> bool:
        """
        Check if path should be excluded based on exclude_folders.

        Excludes paths where:
        1. Any folder name in the path exactly matches an excluded folder name, OR
        2. Any folder name in the path contains an excluded folder name as a substring, OR
        3. The full path (as a string) contains an excluded folder name or path pattern

        Examples:
        - exclude_folders = ["test"] will exclude:
          * "tests" (exact match)
          * "test_utils" (contains "test")
          * "integration_tests" (contains "test")
          * "src/tests/unit/file.py" (path contains "test")
        - exclude_folders = ["vendor"] will exclude: "vendor", "vendors", "vendor_files"
        - exclude_folders = ["tests/unit"] will exclude any path containing "tests/unit"
        """
        # Normalize path separators for cross-platform compatibility
        path_str = str(path).replace("\\", "/")

        # Check if full path contains any excluded name (for path-based exclusions)
        for excluded in self.exclude_folders:
            excluded_normalized = excluded.replace("\\", "/")
            if excluded_normalized in path_str:
                return True

        # Check individual path parts for folder name matches
        for part in path.parts:
            # Check exact match
            if part in self.exclude_folders:
                return True
            # Check if any excluded folder name is contained in this path part
            for excluded in self.exclude_folders:
                # Only check folder name, not path patterns, for substring matching
                if "/" not in excluded and "\\" not in excluded:
                    if excluded in part:
                        return True

        return False

    async def list_directory(self, path: str = ".") -> dict[str, Any]:
        """
        List contents of a directory.

        Args:
            path: Directory path relative to base_dir

        Returns:
            Dictionary with:
                - path: The requested path
                - items: List of items with name, type, and path
                - count: Number of items
            Or error dict if path doesn't exist or isn't a directory
        """
        target_path = self._resolve_safe_path(path)

        if not await aiofiles.os.path.exists(target_path):
            return {"error": f"Path does not exist: {path}"}
        if not await aiofiles.os.path.isdir(target_path):
            return {"error": f"Path is not a directory: {path}"}

        items = []
        for entry in os.scandir(target_path):
            if self.should_exclude(Path(entry.path)):
                continue

            relative_path = Path(entry.path).relative_to(self.base_dir)
            items.append(
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "path": str(relative_path),
                }
            )

        return {"path": path, "items": items, "count": len(items)}

    async def read_file(self, file_path: str) -> dict[str, Any]:
        """
        Read contents of a file.

        Args:
            file_path: File path relative to base_dir

        Returns:
            Dictionary with:
                - path: The requested path
                - content: File contents as string
                - size: Content length in characters
                - lines: Number of lines
            Or error dict if file doesn't exist or can't be read
        """
        target_file = self._resolve_safe_path(file_path)

        if not await aiofiles.os.path.exists(target_file):
            return {"error": f"File does not exist: {file_path}"}
        if not await aiofiles.os.path.isfile(target_file):
            return {"error": f"Path is not a file: {file_path}"}

        try:
            async with aiofiles.open(target_file, "r", encoding="utf-8") as f:
                content = await f.read()
            return {
                "path": file_path,
                "content": content,
                "size": len(content),
                "lines": len(content.splitlines()),
            }
        except UnicodeDecodeError:
            return {"error": f"Cannot read file (binary or non-UTF8): {file_path}"}

    async def search_files(self, directory: str, pattern: str) -> dict[str, Any]:
        """
        Search for files matching a glob pattern.

        Args:
            directory: Directory to search in (relative to base_dir)
            pattern: Glob pattern (e.g., "**/*.py" for recursive Python files)

        Returns:
            Dictionary with:
                - directory: The searched directory
                - pattern: The glob pattern used
                - matches: List of matching items with name, type, and path
                - count: Number of matches
        """
        target_dir = self._resolve_safe_path(directory)

        if not await aiofiles.os.path.exists(target_dir):
            return {"error": f"Directory does not exist: {directory}"}

        matches = []
        for match in target_dir.glob(pattern):
            if self.should_exclude(match):
                continue
            relative_path = match.relative_to(self.base_dir)
            matches.append(
                {
                    "name": match.name,
                    "type": "directory" if match.is_dir() else "file",
                    "path": str(relative_path),
                }
            )

        return {
            "directory": directory,
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
        }

    async def get_directory_tree(self, path: str = ".", max_depth: int = 3) -> dict[str, Any]:
        """
        Get a tree view of the directory structure.

        Args:
            path: Directory path relative to base_dir
            max_depth: Maximum depth to traverse (default: 3)

        Returns:
            Dictionary with:
                - path: The requested path
                - max_depth: The depth used
                - tree: String representation of the directory tree
        """
        target_path = self._resolve_safe_path(path)

        if not await aiofiles.os.path.exists(target_path):
            return {"error": f"Path does not exist: {path}"}
        if not await aiofiles.os.path.isdir(target_path):
            return {"error": f"Path is not a directory: {path}"}

        tree_lines = []

        for root, dirs, files in os.walk(target_path):
            root_path = Path(root)

            # Filter excluded directories - check if directory name matches or contains excluded names
            filtered_dirs = []
            for d in dirs:
                dir_path = root_path / d
                if not self.should_exclude(dir_path):
                    filtered_dirs.append(d)
            dirs[:] = filtered_dirs

            # Calculate depth
            try:
                relative_path = root_path.relative_to(target_path)
                depth = len(relative_path.parts)
            except ValueError:
                depth = 0

            if depth >= max_depth:
                dirs[:] = []
                continue

            indent = "  " * depth
            if depth > 0:
                tree_lines.append(f"{indent}{root_path.name}/")

            for file in sorted(files):
                tree_lines.append(f"{indent}  {file}")

            dirs.sort()

        result_tree = (
            f"{target_path.name}/\n" + "\n".join(tree_lines) if tree_lines else f"{target_path.name}/\n(empty)"
        )

        return {"path": path, "max_depth": max_depth, "tree": result_tree}

    async def get_file_info(self, file_path: str) -> dict[str, Any]:
        """
        Get detailed information about a file.

        Args:
            file_path: File path relative to base_dir

        Returns:
            Dictionary with file metadata (path, name, type, size, modified, extension)
            Or error dict if file doesn't exist
        """
        target_file = self._resolve_safe_path(file_path)

        if not await aiofiles.os.path.exists(target_file):
            return {"error": f"File does not exist: {file_path}"}

        stat_info = await aiofiles.os.stat(target_file)

        return {
            "path": file_path,
            "name": target_file.name,
            "type": "directory" if target_file.is_dir() else "file",
            "size": stat_info.st_size,
            "size_human": self._format_size(stat_info.st_size),
            "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "extension": target_file.suffix if target_file.is_file() else None,
        }

    async def read_multiple_files(self, file_paths: list[str]) -> dict[str, Any]:
        """
        Read contents of multiple files at once.

        Args:
            file_paths: List of file paths relative to base_dir

        Returns:
            Dictionary with:
                - files_requested: Number of files requested
                - files_read: Number successfully read
                - files: List of file results
        """
        results = []

        for file_path in file_paths:
            result = await self.read_file(file_path)
            if "error" in result:
                results.append({"path": file_path, "error": result["error"]})
            else:
                results.append({**result, "success": True})

        return {
            "files_requested": len(file_paths),
            "files_read": sum(1 for r in results if r.get("success", False)),
            "files": results,
        }

    @staticmethod
    def _format_size(size: int) -> str:
        """Format size in bytes to human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def get_tool_definitions(self) -> list[dict]:
        """
        Return tool definitions for LLM function calling.

        These definitions follow the OpenAI/Gemini function calling schema
        and can be used directly with LLM APIs.

        Returns:
            List of tool definition dictionaries
        """
        return [
            {
                "name": "list_directory",
                "description": "List all files and directories in a given path",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list. Use '.' for root.",
                        }
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "read_file",
                "description": "Read and return the complete contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file to read",
                        }
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "search_files",
                "description": "Search for files matching a glob pattern. Use '**' for recursive.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "The directory to search in",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern (e.g., '**/*.py')",
                        },
                    },
                    "required": ["directory", "pattern"],
                },
            },
            {
                "name": "get_directory_tree",
                "description": "Get a tree view of the directory structure",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The directory path"},
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum depth (default: 3)",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "get_file_info",
                "description": "Get detailed information about a file (size, modified date, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file",
                        }
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "read_multiple_files",
                "description": "Read contents of multiple files at once",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Array of file paths to read",
                        }
                    },
                    "required": ["file_paths"],
                },
            },
        ]

    async def execute_tool(self, tool_name: str, args: dict) -> dict[str, Any]:
        """
        Execute a tool by name with given arguments.

        This method is useful for LLM function calling where the LLM
        returns a tool name and arguments.

        Args:
            tool_name: Name of the tool to execute
            args: Dictionary of arguments for the tool

        Returns:
            Tool execution result dictionary
        """
        tool_map = {
            "list_directory": self.list_directory,
            "read_file": self.read_file,
            "search_files": self.search_files,
            "get_directory_tree": self.get_directory_tree,
            "get_file_info": self.get_file_info,
            "read_multiple_files": self.read_multiple_files,
        }

        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            tool_func = tool_map[tool_name]
            result = await tool_func(**args)
            return result
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
