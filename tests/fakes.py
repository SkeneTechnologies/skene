"""Shared test doubles for core/server tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, AsyncGenerator

from skene.analyzers.journey.models import Evidence, Journey, Milestone, Product, Stage
from skene.llm.agent_loop import AssistantTurn, Message, Tool
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
