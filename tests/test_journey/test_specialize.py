"""Tests for the Step 0 specialize step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncGenerator

import pytest

from skene.analyzers.journey.specialize import (
    SpecializedStages,
    gather_signals,
    specialize_stages,
)
from skene.analyzers.journey.stages import STAGES
from skene.llm.base import LLMClient


class _FakeLLM(LLMClient):
    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        self.calls.append(prompt)
        if not self._responses:
            raise AssertionError("fake LLM ran out of responses")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return (nxt, None)

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "fake"

    def get_provider_name(self) -> str:
        return "fake"


def _seven_stages_payload(prefix: str = "X") -> dict:
    return {
        s.id: {
            "name": f"{prefix} {s.name}",
            "subtitle": f"{prefix} {s.subtitle}",
            "description": f"{prefix} desc for {s.id}",
            "examples": [f"{prefix} ex1", f"{prefix} ex2"],
        }
        for s in STAGES
    }


def test_gather_signals_reads_readme_and_manifest(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Ballpark\n\nAI estimate widget.")
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "ballpark",
                "description": "AI estimate widget",
                "keywords": ["ai", "estimate"],
            }
        )
    )
    signals = gather_signals(tmp_path)
    assert "Ballpark" in signals["readme"]
    assert "ballpark" in signals["manifest"]
    assert "ai" in signals["manifest"]
    assert signals["routes"] == ""


def test_gather_signals_handles_missing_files(tmp_path: Path):
    signals = gather_signals(tmp_path)
    assert signals == {"readme": "", "manifest": "", "routes": ""}


def test_specialized_stages_overlays_onto_canonical():
    spec = SpecializedStages.model_validate(_seven_stages_payload(prefix="X"))
    out = spec.to_stage_defs(STAGES)
    assert len(out) == 7
    assert out[0].id == "discovery"
    assert out[0].name == "X Discovery"
    # IDs and order stay canonical
    assert [s.id for s in out] == [s.id for s in STAGES]
    assert [s.order for s in out] == [s.order for s in STAGES]


@pytest.mark.asyncio
async def test_specialize_happy_path(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Estimator")
    llm = _FakeLLM([json.dumps(_seven_stages_payload(prefix="EST"))])
    stages = await specialize_stages(tmp_path, "Estimator", llm)
    assert stages != STAGES
    assert stages[0].name == "EST Discovery"


@pytest.mark.asyncio
async def test_specialize_falls_back_on_llm_error(tmp_path: Path):
    llm = _FakeLLM([RuntimeError("boom")])
    stages = await specialize_stages(tmp_path, "X", llm)
    assert stages == STAGES


@pytest.mark.asyncio
async def test_specialize_falls_back_on_non_json(tmp_path: Path):
    llm = _FakeLLM(["here are some stages"])
    stages = await specialize_stages(tmp_path, "X", llm)
    assert stages == STAGES


@pytest.mark.asyncio
async def test_specialize_falls_back_on_missing_stage(tmp_path: Path):
    payload = _seven_stages_payload()
    del payload["virality"]  # missing one — schema enforces all seven
    llm = _FakeLLM([json.dumps(payload)])
    stages = await specialize_stages(tmp_path, "X", llm)
    assert stages == STAGES
