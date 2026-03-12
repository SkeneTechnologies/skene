"""Tests for the AnalysisContext and StepResult classes."""

from skene.strategies.context import AnalysisContext, StepResult


class TestStepResult:
    """Tests for StepResult class."""

    def test_success_when_no_error(self):
        """Should return success=True when no error."""
        result = StepResult(step_name="test_step")
        assert result.success is True

    def test_not_success_when_error(self):
        """Should return success=False when error exists."""
        result = StepResult(step_name="test_step", error="Something failed")
        assert result.success is False

    def test_default_values(self):
        """Should have correct default values."""
        result = StepResult(step_name="test_step")

        assert result.step_name == "test_step"
        assert result.data == {}
        assert result.files_read == []
        assert result.tokens_used == 0
        assert result.error is None

    def test_stores_data(self):
        """Should store provided data."""
        result = StepResult(
            step_name="select_files",
            data={"files": ["a.py", "b.py"]},
            files_read=["a.py", "b.py"],
            tokens_used=150,
        )

        assert result.data == {"files": ["a.py", "b.py"]}
        assert result.files_read == ["a.py", "b.py"]
        assert result.tokens_used == 150


class TestAnalysisContext:
    """Tests for AnalysisContext class."""

    def test_initialization(self):
        """Should initialize with request."""
        context = AnalysisContext(request="Analyze this repo")
        assert context.request == "Analyze this repo"
        assert context.step_results == []

    def test_get_set_data(self):
        """Should get and set data correctly."""
        context = AnalysisContext(request="test")

        context.set("key1", "value1")
        context.set("key2", [1, 2, 3])

        assert context.get("key1") == "value1"
        assert context.get("key2") == [1, 2, 3]

    def test_get_with_default(self):
        """Should return default for missing keys."""
        context = AnalysisContext(request="test")

        assert context.get("missing") is None
        assert context.get("missing", "default") == "default"
        assert context.get("missing", []) == []

    def test_add_step_result(self):
        """Should accumulate step results."""
        context = AnalysisContext(request="test")

        result1 = StepResult(
            step_name="step1",
            data={"selected_files": ["a.py"]},
            files_read=["a.py"],
            tokens_used=100,
        )

        result2 = StepResult(
            step_name="step2",
            data={"analysis": "done"},
            files_read=["b.py"],
            tokens_used=200,
        )

        context.add_step_result("step1", result1)
        context.add_step_result("step2", result2)

        assert len(context.step_results) == 2
        assert context.metadata.steps_completed == 2

    def test_add_step_result_merges_data(self):
        """Should merge step data into accumulated data."""
        context = AnalysisContext(request="test")

        result = StepResult(
            step_name="step1",
            data={"files": ["a.py", "b.py"]},
        )
        context.add_step_result("step1", result)

        # Data should be accessible via get()
        assert context.get("files") == ["a.py", "b.py"]

    def test_add_step_result_tracks_files_and_tokens(self):
        """Should track files read and tokens used."""
        context = AnalysisContext(request="test")

        result = StepResult(
            step_name="step1",
            files_read=["a.py", "b.py"],
            tokens_used=500,
        )
        context.add_step_result("step1", result)

        assert context.metadata.files_read == ["a.py", "b.py"]
        assert context.metadata.tokens_used == 500

    def test_get_all_data(self):
        """Should return all accumulated data."""
        context = AnalysisContext(request="test")

        context.set("key1", "value1")
        context.add_step_result(
            "step1",
            StepResult(step_name="step1", data={"key2": "value2"}),
        )

        all_data = context.get_all_data()
        assert all_data == {"key1": "value1", "key2": "value2"}

    def test_get_step_result(self):
        """Should retrieve specific step result by name."""
        context = AnalysisContext(request="test")

        result = StepResult(step_name="my_step", data={"foo": "bar"})
        context.add_step_result("my_step", result)

        retrieved = context.get_step_result("my_step")
        assert retrieved is not None
        assert retrieved.step_name == "my_step"
        assert retrieved.data == {"foo": "bar"}

    def test_get_step_result_returns_none_for_missing(self):
        """Should return None for missing step."""
        context = AnalysisContext(request="test")
        assert context.get_step_result("nonexistent") is None

    def test_to_result_success(self):
        """Should create successful result when all steps succeed."""
        context = AnalysisContext(request="test")

        context.add_step_result(
            "step1",
            StepResult(step_name="step1", data={"key": "value"}),
        )

        result = context.to_result()

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_to_result_error_when_step_fails(self):
        """Should create error result when a step fails."""
        context = AnalysisContext(request="test")

        context.add_step_result(
            "step1",
            StepResult(step_name="step1", error="Step 1 failed"),
        )

        result = context.to_result()

        assert result.success is False
        assert "step1" in result.error
        assert "Step 1 failed" in result.error

    def test_to_result_reports_first_error(self):
        """Should report first failing step."""
        context = AnalysisContext(request="test")

        context.add_step_result(
            "step1",
            StepResult(step_name="step1", data={"ok": True}),
        )
        context.add_step_result(
            "step2",
            StepResult(step_name="step2", error="Step 2 failed"),
        )
        context.add_step_result(
            "step3",
            StepResult(step_name="step3", error="Step 3 also failed"),
        )

        result = context.to_result()

        assert result.success is False
        assert "step2" in result.error
