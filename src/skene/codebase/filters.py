"""
File and directory filtering utilities.
"""

# Default folders to exclude when scanning repositories
DEFAULT_EXCLUDE_FOLDERS = [
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".idea",
    ".vscode",
    ".DS_Store",
    "venv",
    ".venv",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".cache",
]


def should_exclude(path_parts: tuple[str, ...], exclude_folders: set[str]) -> bool:
    """
    Check if a path should be excluded based on folder names.

    Args:
        path_parts: Tuple of path components (from Path.parts)
        exclude_folders: Set of folder names to exclude

    Returns:
        True if the path should be excluded, False otherwise
    """
    for part in path_parts:
        if part in exclude_folders:
            return True
    return False
