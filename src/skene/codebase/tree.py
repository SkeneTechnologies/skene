"""
Directory tree building utilities.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from skene.codebase.filters import DEFAULT_EXCLUDE_FOLDERS


def build_directory_tree(
    folder_path: str | Path,
    exclude_folders: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Generate JSON structure of files and folders iteratively.

    This function creates a hierarchical representation of a directory structure
    where each entry is a dictionary with 'name', 'type', and optionally 'children'
    for directories.

    Args:
        folder_path: Root directory path to build tree from
        exclude_folders: Additional folder names to exclude (merged with defaults)

    Returns:
        List of dictionaries representing the directory tree structure.
        Each dictionary has the format:
        - For files: {"name": str, "type": "file"}
        - For directories: {"name": str, "type": "directory", "children": List}

    Example:
        tree = build_directory_tree("/path/to/repo")
        # Returns:
        # [
        #     {"name": "src", "type": "directory", "children": [...]},
        #     {"name": "README.md", "type": "file"},
        # ]
    """
    # Merge provided excludes with defaults
    if exclude_folders is None:
        exclude_folders = []

    all_excludes = set(DEFAULT_EXCLUDE_FOLDERS + exclude_folders)

    def _build_tree_iterative(root_path: Path) -> list[dict[str, Any]]:
        """
        Internal iterative function to build the tree structure.
        Uses a stack-based approach to avoid deep recursion.

        Args:
            root_path: Root path to process

        Returns:
            List of items (files and directories) at the root level
        """
        if not root_path.is_dir():
            return []

        # Root container for the result
        root_items: list[dict[str, Any]] = []

        # Stack entries: (current_path, parent_children_list)
        # We'll process directories level by level
        stack: list[tuple[Path, list[dict[str, Any]]]] = [(root_path, root_items)]

        while stack:
            current_path, parent_list = stack.pop()

            try:
                # Get entries as an iterator to avoid loading all at once
                entries = list(current_path.iterdir())

                # Sort for consistent output (dirs first, then alphabetically)
                entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

                for entry in entries:
                    # Skip excluded directories
                    if entry.name in all_excludes:
                        continue

                    if entry.is_dir():
                        # Create directory item with empty children list
                        children: list[dict[str, Any]] = []
                        item: dict[str, Any] = {
                            "name": entry.name,
                            "type": "directory",
                            "children": children,
                        }
                        parent_list.append(item)
                        # Add to stack to process this directory's contents
                        stack.append((entry, children))
                    else:
                        # Create file item
                        item = {"name": entry.name, "type": "file"}
                        parent_list.append(item)

            except PermissionError:
                logger.warning(f"Permission denied accessing: {current_path}")
            except Exception as e:
                logger.error(f"Error processing directory {current_path}: {e}")

        return root_items

    folder_path = Path(folder_path) if isinstance(folder_path, str) else folder_path
    logger.info(f"Building directory tree for: {folder_path}")
    tree = _build_tree_iterative(folder_path)
    logger.debug(f"Built directory tree with {len(tree)} top-level items")
    return tree
