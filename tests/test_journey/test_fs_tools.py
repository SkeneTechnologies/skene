"""Tests for the FsToolset and code agent (Step 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.tools.fs_tools import FsToolset


def _build_repo(tmp_path: Path) -> Path:
    """Build a tiny synthetic repo. Reused across tests in this module."""
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "api" / "signup.ts").write_text(
        "export async function POST() {\n  // create user\n  await analytics.track('account_created');\n}\n"
    )
    (tmp_path / "src" / "api" / "estimates.ts").write_text("export async function POST() {\n  // create estimate\n}\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.ts").write_text("// should be ignored\nanalytics.track('vendor')\n")
    (tmp_path / "README.md").write_text("# Test repo\n")
    return tmp_path


def test_list_directory_filters_ignored_dirs(tmp_path: Path):
    repo = _build_repo(tmp_path)
    toolset = FsToolset(repo, [])
    entries = toolset._list_directory(".")
    assert not isinstance(entries, dict)
    names = {e.name for e in entries}
    assert "src" in names
    assert "README.md" in names
    assert "node_modules" not in names  # filtered


def test_list_directory_rejects_absolute_path(tmp_path: Path):
    repo = _build_repo(tmp_path)
    toolset = FsToolset(repo, [])
    out = toolset._list_directory("/etc")
    assert isinstance(out, dict)
    assert "error" in out


def test_list_directory_rejects_parent_traversal(tmp_path: Path):
    repo = _build_repo(tmp_path)
    toolset = FsToolset(repo, [])
    out = toolset._list_directory("../..")
    assert isinstance(out, dict)
    assert "error" in out


def test_read_file_returns_text_and_truncates(tmp_path: Path):
    repo = _build_repo(tmp_path)
    big = repo / "big.txt"
    big.write_text("x" * 1000)
    toolset = FsToolset(repo, [])
    out = toolset._read_file("big.txt", max_bytes=100)
    assert isinstance(out, str)
    assert "[truncated at 100 bytes]" in out


def test_read_file_missing(tmp_path: Path):
    repo = _build_repo(tmp_path)
    toolset = FsToolset(repo, [])
    out = toolset._read_file("nope.txt")
    assert isinstance(out, dict)
    assert "file not found" in out["error"]


def test_search_files_finds_matches(tmp_path: Path):
    repo = _build_repo(tmp_path)
    toolset = FsToolset(repo, [])
    hits = toolset._search_files(r"analytics\.track")
    assert not isinstance(hits, dict)
    # Should hit signup.ts but NOT node_modules/junk.ts
    paths = {h.path for h in hits}
    assert any("signup.ts" in p for p in paths)
    assert not any("node_modules" in p for p in paths)


def test_search_files_invalid_regex(tmp_path: Path):
    repo = _build_repo(tmp_path)
    toolset = FsToolset(repo, [])
    out = toolset._search_files("[unbalanced")
    assert isinstance(out, dict)
    assert "invalid regex" in out["error"]


def test_emit_milestone_requires_real_file(tmp_path: Path):
    repo = _build_repo(tmp_path)
    collector: list[CandidateMilestone] = []
    toolset = FsToolset(repo, collector)
    out = toolset._emit_milestone(
        proposed_id="ghost",
        name="Ghost",
        description="X",
        path="src/api/ghost.ts",  # does not exist
        reason="?",
    )
    assert isinstance(out, dict)
    assert "must be a real file" in out["error"]
    assert collector == []


def test_emit_milestone_records_into_collector(tmp_path: Path):
    repo = _build_repo(tmp_path)
    collector: list[CandidateMilestone] = []
    toolset = FsToolset(repo, collector)
    ack = toolset._emit_milestone(
        proposed_id="account_created",
        name="Account Created",
        description="Signup endpoint",
        path="src/api/signup.ts",
        reason="POST handler creates user row",
    )
    assert ack == "recorded account_created"
    assert collector[0].evidence[0].source.value == "code"
    assert collector[0].evidence[0].path == "src/api/signup.ts"


def test_init_rejects_missing_repo(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        FsToolset(tmp_path / "nope", [])


@pytest.mark.asyncio
async def test_as_tools_handlers_dispatch(tmp_path: Path):
    repo = _build_repo(tmp_path)
    toolset = FsToolset(repo, [])
    by_name = {t.name: t for t in toolset.as_tools()}

    entries = await by_name["list_directory"].handler({"path": "."})
    assert isinstance(entries, list)

    hits = await by_name["search_files"].handler({"pattern": r"analytics\.track"})
    assert isinstance(hits, list)

    text = await by_name["read_file"].handler({"path": "README.md"})
    assert "Test repo" in text


@pytest.mark.asyncio
async def test_run_code_agent_with_scripted_llm(tmp_path: Path):
    """Smoke test the code agent against a fake LLM that emits one milestone."""
    from skene.analyzers.journey.code_agent import run_code_agent
    from skene.llm.agent_loop import AssistantTurn, Message, Tool, ToolCall
    from skene.llm.base import LLMClient

    repo = _build_repo(tmp_path)

    class _Scripted(LLMClient):
        def __init__(self):
            self._step = 0

        async def generate_content_with_usage(self, prompt: str):
            return ("", None)

        async def generate_content_stream(self, prompt: str):
            if False:
                yield ""

        def get_model_name(self) -> str:
            return "scripted"

        def get_provider_name(self) -> str:
            return "scripted"

        async def generate_with_tools(self, messages: list[Message], tools: list[Tool]) -> AssistantTurn:
            self._step += 1
            if self._step == 1:
                return AssistantTurn(
                    text=None,
                    tool_calls=[ToolCall(id="c1", name="list_directory", arguments={})],
                )
            if self._step == 2:
                return AssistantTurn(
                    text=None,
                    tool_calls=[
                        ToolCall(
                            id="c2",
                            name="emit_milestone",
                            arguments={
                                "proposed_id": "signup",
                                "name": "Signup",
                                "description": "POST signup handler",
                                "path": "src/api/signup.ts",
                                "reason": "Creates user row + emits analytics event",
                                "tracked_event": "account_created",
                                "confidence": 0.9,
                            },
                        )
                    ],
                )
            return AssistantTurn(text="done")

    client = _Scripted()
    candidates = await run_code_agent(repo, client, max_turns=10)
    assert len(candidates) == 1
    assert candidates[0].proposed_id == "signup"
    assert candidates[0].evidence[0].source.value == "code"
    assert candidates[0].tracked_event == "account_created"
