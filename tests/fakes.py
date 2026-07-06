"""Shared test doubles for core/server tests."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, AsyncGenerator

from skene.analyzers.journey.models import Evidence, Journey, Milestone, Product, Stage
from skene.llm.agent_loop import AssistantTurn, Message, Tool, ToolCall
from skene.llm.base import LLMClient


class ScriptedClient(LLMClient):
    """Returns a queued AssistantTurn per ``generate_with_tools`` call."""

    def __init__(self, turns: list[AssistantTurn]) -> None:
        self._turns = list(turns)

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        raise NotImplementedError

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "scripted-model"

    def get_provider_name(self) -> str:
        return "scripted"

    async def generate_with_tools(self, messages: list[Message], tools: list[Tool]) -> AssistantTurn:
        if not self._turns:
            raise AssertionError("scripted client ran out of turns")
        return self._turns.pop(0)


class HangingClient(ScriptedClient):
    """Blocks forever on the first LLM call — for abort/busy tests."""

    def __init__(self) -> None:
        super().__init__([])
        self.called = asyncio.Event()

    async def generate_with_tools(self, messages: list[Message], tools: list[Tool]) -> AssistantTurn:
        self.called.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


def make_journey(product: str = "TestProduct") -> Journey:
    """Smallest Journey the models accept: one stage, one milestone."""
    return Journey(
        product=Product(name=product, generated_at=datetime.now(UTC)),
        stages=[
            Stage(
                id="onboarding",
                order=1,
                name="Onboarding",
                milestones=[
                    Milestone(
                        id="signs_up",
                        order=1,
                        name="User signs up",
                        description="Creates an account",
                        evidence=[Evidence(source="code", reason="signup route", path="auth/signup.ts")],
                    )
                ],
            )
        ],
    )


def turn(text: str | None = None, tool_calls: list | None = None, usage: dict[str, int] | None = None) -> Any:
    return AssistantTurn(text=text, tool_calls=tool_calls or [], usage=usage)


# Stage assignments the fake classifier hands out, keyed by milestone name.
PARITY_STAGE_MAP: dict[str, str] = {
    "Account Created": "onboarding",
    "Invite Sent": "virality",
    "Landing Page": "discovery",
}


class JourneyFakeLLM(LLMClient):
    """Deterministic fake that drives the whole agentic journey flow.

    It tells the callers apart by their system prompt: the schema subagent
    ("parsed database schema"), the code subagent ("explore a codebase"),
    and everything else is treated as the main skene agent. Plain
    ``generate_content`` calls are answered as the classifier, using
    ``stage_map`` (milestone name → stage id).

    The same instance drove the retired deterministic pipeline when the
    parity golden file was generated (see ``tests/fixtures/parity``), so
    the agentic flow is expected to reproduce that output byte-for-byte
    modulo ``generated_at``.
    """

    def __init__(self, stage_map: dict[str, str] | None = None) -> None:
        self._stage_map = dict(PARITY_STAGE_MAP if stage_map is None else stage_map)
        self._steps: dict[str, int] = {"main": 0, "schema": 0, "code": 0}

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        match = re.search(r"^Milestone: (.+)$", prompt, flags=re.MULTILINE)
        name = match.group(1).strip() if match else ""
        stage = self._stage_map.get(name, "engagement")
        return json.dumps({"stage_id": stage, "confidence": 0.85, "reason": "fake classifier"}), None

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if False:
            yield ""
        raise NotImplementedError

    def get_model_name(self) -> str:
        return "journey-fake"

    def get_provider_name(self) -> str:
        return "fake"

    async def generate_with_tools(self, messages: list[Message], tools: list[Tool]) -> AssistantTurn:
        system = (messages[0].content or "") if messages else ""
        if "parsed database schema" in system:
            return self._schema_turn()
        if "explore a codebase" in system:
            return self._code_turn()
        return self._main_turn()

    def _schema_turn(self) -> AssistantTurn:
        self._steps["schema"] += 1
        if self._steps["schema"] == 1:
            return AssistantTurn(tool_calls=[ToolCall(id="s1", name="list_schema_files", arguments={})])
        if self._steps["schema"] == 2:
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        id="s2",
                        name="emit_milestone",
                        arguments={
                            "proposed_id": "account_created",
                            "name": "Account Created",
                            "description": "users table row inserted",
                            "table": "public.users",
                            "reason": "users table holds account state",
                            "confidence": 0.9,
                        },
                    ),
                    ToolCall(
                        id="s3",
                        name="emit_milestone",
                        arguments={
                            "proposed_id": "invite_sent",
                            "name": "Invite Sent",
                            "description": "invites table row inserted",
                            "table": "public.invites",
                            "reason": "invites reference a sender",
                            "confidence": 0.8,
                        },
                    ),
                ]
            )
        return AssistantTurn(text="schema done")

    def _code_turn(self) -> AssistantTurn:
        self._steps["code"] += 1
        if self._steps["code"] == 1:
            return AssistantTurn(tool_calls=[ToolCall(id="c1", name="list_directory", arguments={})])
        if self._steps["code"] == 2:
            return AssistantTurn(
                tool_calls=[
                    ToolCall(
                        id="c2",
                        name="emit_milestone",
                        arguments={
                            "proposed_id": "landing_page",
                            "name": "Landing Page",
                            "description": "marketing route",
                            "path": "index.tsx",
                            "reason": "served at /",
                            "confidence": 0.9,
                        },
                    )
                ]
            )
        return AssistantTurn(text="code done")

    def _main_turn(self) -> AssistantTurn:
        self._steps["main"] += 1
        if self._steps["main"] == 1:
            return AssistantTurn(
                tool_calls=[
                    ToolCall(id="m1", name="task", arguments={"agent": "code", "prompt": "Explore the repo."}),
                    ToolCall(id="m2", name="task", arguments={"agent": "schema", "prompt": "Explore the schema."}),
                ]
            )
        if self._steps["main"] == 2:
            return AssistantTurn(tool_calls=[ToolCall(id="m3", name="finalize_journey", arguments={})])
        return AssistantTurn(text="Journey analysis complete.")
