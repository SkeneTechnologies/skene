"""Tests for the tree module."""

from pathlib import Path

from skene.codebase.tree import build_directory_tree


class TestBuildDirectoryTree:
    """Tests for build_directory_tree function."""

    def test_returns_list(self, sample_repo_path: Path):
        """Should return a list."""
        result = build_directory_tree(sample_repo_path)
        assert isinstance(result, list)

    def test_includes_files_and_directories(self, sample_repo_path: Path):
        """Should include both files and directories."""
        result = build_directory_tree(sample_repo_path)

        names = [item["name"] for item in result]
        types = [item["type"] for item in result]

        assert "src" in names
        assert "README.md" in names
        assert "directory" in types
        assert "file" in types

    def test_directories_have_children(self, sample_repo_path: Path):
        """Directories should have children list."""
        result = build_directory_tree(sample_repo_path)

        src_dir = next(item for item in result if item["name"] == "src")
        assert "children" in src_dir
        assert isinstance(src_dir["children"], list)
        assert len(src_dir["children"]) > 0

    def test_excludes_git_by_default(self, sample_repo_path: Path):
        """Should exclude .git directory by default."""
        result = build_directory_tree(sample_repo_path)

        names = [item["name"] for item in result]
        assert ".git" not in names

    def test_custom_exclude_folders(self, sample_repo_path: Path):
        """Should support custom exclude folders."""
        result = build_directory_tree(sample_repo_path, exclude_folders=["src"])

        names = [item["name"] for item in result]
        assert "src" not in names
        assert "README.md" in names

    def test_returns_empty_for_nonexistent_path(self, tmp_path: Path):
        """Should return empty list for non-existent path."""
        nonexistent = tmp_path / "does_not_exist"
        result = build_directory_tree(nonexistent)
        assert result == []

    def test_returns_empty_for_file_path(self, sample_repo_path: Path):
        """Should return empty list when given a file path."""
        file_path = sample_repo_path / "README.md"
        result = build_directory_tree(file_path)
        assert result == []

    def test_accepts_string_path(self, sample_repo_path: Path):
        """Should accept string paths."""
        result = build_directory_tree(str(sample_repo_path))
        assert isinstance(result, list)
        assert len(result) > 0

    def test_nested_directory_structure(self, sample_repo_path: Path):
        """Should correctly handle nested directories."""
        result = build_directory_tree(sample_repo_path)

        src_dir = next(item for item in result if item["name"] == "src")
        children_names = [child["name"] for child in src_dir["children"]]

        assert "main.py" in children_names
        assert "utils.py" in children_names

    def test_handles_empty_directory(self, tmp_path: Path):
        """Should handle empty directories."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = build_directory_tree(empty_dir)
        assert result == []


class TestBuildDirectoryTreeEdgeCases:
    """Edge case tests for build_directory_tree."""

    def test_deeply_nested_structure(self, tmp_path: Path):
        """Should handle deeply nested structures."""
        current = tmp_path
        for i in range(5):
            current = current / f"level{i}"
            current.mkdir()

        (current / "deep_file.txt").write_text("content")

        result = build_directory_tree(tmp_path)
        assert len(result) == 1
        assert result[0]["type"] == "directory"

    def test_multiple_files_same_level(self, tmp_path: Path):
        """Should include all files at the same level."""
        for i in range(5):
            (tmp_path / f"file{i}.txt").write_text(f"content {i}")

        result = build_directory_tree(tmp_path)
        assert len(result) == 5
        assert all(item["type"] == "file" for item in result)

    def test_mixed_content(self, tmp_path: Path):
        """Should handle mixed files and directories."""
        (tmp_path / "file.txt").write_text("content")
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "nested.txt").write_text("nested")

        result = build_directory_tree(tmp_path)

        assert len(result) == 2
        file_item = next(item for item in result if item["type"] == "file")
        dir_item = next(item for item in result if item["type"] == "directory")

        assert file_item["name"] == "file.txt"
        assert dir_item["name"] == "dir1"
        assert len(dir_item["children"]) == 1
