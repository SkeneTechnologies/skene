"""Tests for the AnalysisResult and AnalysisMetadata classes."""

import time
from datetime import datetime

from skene.strategies.base import AnalysisMetadata, AnalysisResult


class TestAnalysisMetadata:
    """Tests for AnalysisMetadata class."""

    def test_default_values(self):
        """Should have correct default values."""
        meta = AnalysisMetadata()

        assert isinstance(meta.started_at, datetime)
        assert meta.completed_at is None
        assert meta.total_steps == 0
        assert meta.steps_completed == 0
        assert meta.files_read == []
        assert meta.tokens_used == 0
        assert meta.model_name is None
        assert meta.provider_name is None

    def test_mark_complete_sets_completed_at(self):
        """Should set completed_at when marked complete."""
        meta = AnalysisMetadata()
        assert meta.completed_at is None

        meta.mark_complete()

        assert meta.completed_at is not None
        assert isinstance(meta.completed_at, datetime)

    def test_duration_ms_returns_none_when_incomplete(self):
        """Should return None for duration when not complete."""
        meta = AnalysisMetadata()
        assert meta.duration_ms is None

    def test_duration_ms_calculates_correctly(self):
        """Should calculate duration in milliseconds."""
        meta = AnalysisMetadata()

        # Small sleep to ensure measurable duration
        time.sleep(0.01)
        meta.mark_complete()

        assert meta.duration_ms is not None
        assert meta.duration_ms >= 10  # At least 10ms

    def test_can_set_all_fields(self):
        """Should allow setting all fields."""
        meta = AnalysisMetadata(
            total_steps=5,
            steps_completed=3,
            files_read=["a.py", "b.py"],
            tokens_used=1500,
            model_name="gemini-pro",
            provider_name="gemini",
        )

        assert meta.total_steps == 5
        assert meta.steps_completed == 3
        assert meta.files_read == ["a.py", "b.py"]
        assert meta.tokens_used == 1500
        assert meta.model_name == "gemini-pro"
        assert meta.provider_name == "gemini"


class TestAnalysisResult:
    """Tests for AnalysisResult class."""

    def test_default_values(self):
        """Should have correct default values."""
        result = AnalysisResult(success=True)

        assert result.success is True
        assert result.data == {}
        assert result.error is None
        assert isinstance(result.metadata, AnalysisMetadata)

    def test_success_result_factory(self):
        """Should create successful result via factory."""
        result = AnalysisResult.success_result(data={"key": "value", "count": 42})

        assert result.success is True
        assert result.data == {"key": "value", "count": 42}
        assert result.error is None
        assert result.metadata.completed_at is not None

    def test_success_result_with_metadata(self):
        """Should preserve provided metadata."""
        meta = AnalysisMetadata(
            total_steps=3,
            steps_completed=3,
            tokens_used=500,
        )

        result = AnalysisResult.success_result(
            data={"analysis": "complete"},
            metadata=meta,
        )

        assert result.metadata.total_steps == 3
        assert result.metadata.steps_completed == 3
        assert result.metadata.tokens_used == 500
        assert result.metadata.completed_at is not None

    def test_error_result_factory(self):
        """Should create error result via factory."""
        result = AnalysisResult.error_result(error="Something went wrong")

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.data == {}
        assert result.metadata.completed_at is not None

    def test_error_result_with_metadata(self):
        """Should preserve provided metadata on error."""
        meta = AnalysisMetadata(
            total_steps=5,
            steps_completed=2,
            files_read=["a.py"],
        )

        result = AnalysisResult.error_result(
            error="Failed at step 3",
            metadata=meta,
        )

        assert result.metadata.total_steps == 5
        assert result.metadata.steps_completed == 2
        assert result.metadata.files_read == ["a.py"]

    def test_can_create_manually(self):
        """Should allow manual creation."""
        result = AnalysisResult(
            success=True,
            data={"custom": "data"},
            metadata=AnalysisMetadata(tokens_used=100),
        )

        assert result.success is True
        assert result.data == {"custom": "data"}
        assert result.metadata.tokens_used == 100


class TestAnalysisResultEdgeCases:
    """Edge case tests for AnalysisResult."""

    def test_empty_data(self):
        """Should handle empty data dict."""
        result = AnalysisResult.success_result(data={})
        assert result.success is True
        assert result.data == {}

    def test_complex_data(self):
        """Should handle complex nested data."""
        complex_data = {
            "files": ["a.py", "b.py"],
            "analysis": {
                "score": 85,
                "issues": [
                    {"type": "warning", "message": "Unused import"},
                ],
            },
            "metadata": {"version": "1.0"},
        }

        result = AnalysisResult.success_result(data=complex_data)
        assert result.data == complex_data

    def test_empty_error_string(self):
        """Should handle empty error string."""
        result = AnalysisResult.error_result(error="")
        assert result.success is False
        assert result.error == ""
