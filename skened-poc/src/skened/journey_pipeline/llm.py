"""LLM client seam, backed by LiteLLM.

``LLMClient`` is the minimal interface the LLM-driven pipeline steps need:

- ``complete()`` — text-in/text-out, used by the classifier and the brancher.
- ``chat()`` — one tool-use turn, used by the agentic code agent's loop.

``LiteLLMClient`` adapts both onto `litellm.acompletion`, so one client works across
OpenAI / Anthropic / Gemini / local models by model string (e.g. ``"anthropic/claude-..."``,
``"gpt-4o"``, ``"ollama/llama3"``). litellm is imported lazily so it stays an optional dep:
``uv sync --extra llm``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Protocol


def _quiet_litellm_logging() -> None:
    """Silence LiteLLM's noisy provider-preload WARNINGs.

    On import LiteLLM warns that it cannot pre-load the Bedrock/SageMaker event-stream
    shapes (they need ``botocore``, which we don't ship and don't use), and it double-prints
    by propagating those records to the root logger. The env var governs import-time
    verbosity; muting + un-propagating the loggers covers the rest. ``setdefault`` respects
    an explicit user override.
    """
    os.environ.setdefault("LITELLM_LOG", "ERROR")
    for name in ("LiteLLM", "litellm"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.ERROR)
        lg.propagate = False


class LlmAnalysisError(RuntimeError):
    """Raised when an LLM-backed analysis step fails (transport, auth, rate-limit, or
    unusable model output). It is never swallowed: it fails the analysis run so the problem
    surfaces instead of producing a silently-degraded journey."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class AssistantTurn:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # The raw assistant message to append back to the conversation before tool results.
    raw_message: dict = field(default_factory=dict)


class LLMClient(Protocol):
    async def complete(self, prompt: str, *, system: str | None = None) -> str: ...

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AssistantTurn: ...


class LiteLLMClient:
    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.0,
        **completion_kwargs: Any,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.completion_kwargs = completion_kwargs

    def _kwargs(self) -> dict:
        kw: dict[str, Any] = {"model": self.model, "temperature": self.temperature, **self.completion_kwargs}
        if self.api_key:
            kw["api_key"] = self.api_key
        if self.base_url:
            kw["base_url"] = self.base_url
        return kw

    @staticmethod
    def _litellm():
        _quiet_litellm_logging()  # before import: silences import-time provider-preload warnings
        try:
            import litellm
        except ImportError as e:  # pragma: no cover - only when extra missing
            raise RuntimeError(
                "litellm is not installed. Run `uv sync --extra llm` to enable LLM-backed analysis."
            ) from e
        litellm.suppress_debug_info = True
        _quiet_litellm_logging()  # after import: in case litellm reconfigured its loggers
        return litellm

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        litellm = self._litellm()
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        resp = await litellm.acompletion(messages=messages, **self._kwargs())
        return resp.choices[0].message.content or ""

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> AssistantTurn:
        litellm = self._litellm()
        kwargs = self._kwargs()
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = await litellm.acompletion(messages=messages, **kwargs)
        msg = resp.choices[0].message

        tool_calls: list[ToolCall] = []
        raw_tool_calls: list[dict] = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
            raw_tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
            })

        raw_message: dict = {"role": "assistant", "content": msg.content or ""}
        if raw_tool_calls:
            raw_message["tool_calls"] = raw_tool_calls
        return AssistantTurn(text=msg.content, tool_calls=tool_calls, raw_message=raw_message)
