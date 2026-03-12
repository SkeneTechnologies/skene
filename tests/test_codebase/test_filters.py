"""Tests for the filters module."""

from skene.codebase.filters import DEFAULT_EXCLUDE_FOLDERS, should_exclude


class TestDefaultExcludeFolders:
    """Tests for DEFAULT_EXCLUDE_FOLDERS constant."""

    def test_contains_git_folders(self):
        """Should exclude version control folders."""
        assert ".git" in DEFAULT_EXCLUDE_FOLDERS
        assert ".svn" in DEFAULT_EXCLUDE_FOLDERS
        assert ".hg" in DEFAULT_EXCLUDE_FOLDERS

    def test_contains_python_cache_folders(self):
        """Should exclude Python cache folders."""
        assert "__pycache__" in DEFAULT_EXCLUDE_FOLDERS
        assert ".pytest_cache" in DEFAULT_EXCLUDE_FOLDERS

    def test_contains_node_modules(self):
        """Should exclude node_modules."""
        assert "node_modules" in DEFAULT_EXCLUDE_FOLDERS

    def test_contains_ide_folders(self):
        """Should exclude IDE configuration folders."""
        assert ".idea" in DEFAULT_EXCLUDE_FOLDERS
        assert ".vscode" in DEFAULT_EXCLUDE_FOLDERS

    def test_contains_virtual_env_folders(self):
        """Should exclude virtual environment folders."""
        assert "venv" in DEFAULT_EXCLUDE_FOLDERS
        assert ".venv" in DEFAULT_EXCLUDE_FOLDERS
        assert ".env" in DEFAULT_EXCLUDE_FOLDERS


class TestShouldExclude:
    """Tests for should_exclude function."""

    def test_returns_true_for_excluded_folder(self):
        """Should return True when path contains excluded folder."""
        path_parts = ("src", "node_modules", "package.json")
        exclude_folders = {"node_modules", ".git"}
        assert should_exclude(path_parts, exclude_folders) is True

    def test_returns_false_for_allowed_folder(self):
        """Should return False when path contains no excluded folders."""
        path_parts = ("src", "components", "Button.tsx")
        exclude_folders = {"node_modules", ".git"}
        assert should_exclude(path_parts, exclude_folders) is False

    def test_returns_true_when_excluded_at_start(self):
        """Should detect excluded folder at path start."""
        path_parts = (".git", "config")
        exclude_folders = {".git"}
        assert should_exclude(path_parts, exclude_folders) is True

    def test_returns_true_when_excluded_at_end(self):
        """Should detect excluded folder at path end."""
        path_parts = ("project", "src", "__pycache__")
        exclude_folders = {"__pycache__"}
        assert should_exclude(path_parts, exclude_folders) is True

    def test_returns_false_for_empty_path(self):
        """Should return False for empty path parts."""
        path_parts: tuple[str, ...] = ()
        exclude_folders = {"node_modules"}
        assert should_exclude(path_parts, exclude_folders) is False

    def test_returns_false_for_empty_excludes(self):
        """Should return False when no folders are excluded."""
        path_parts = ("src", "node_modules", "file.js")
        exclude_folders: set[str] = set()
        assert should_exclude(path_parts, exclude_folders) is False

    def test_partial_match_does_not_exclude(self):
        """Should not exclude partial matches."""
        path_parts = ("my_node_modules_backup", "file.js")
        exclude_folders = {"node_modules"}
        assert should_exclude(path_parts, exclude_folders) is False
