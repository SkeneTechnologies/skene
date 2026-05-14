"""
Debug wrapper for LLM clients that logs all input/output to files.
"""

import time
from datetime import datetime
from typing import AsyncGenerator

from loguru import logger

from skene.llm.agent_loop import AssistantTurn, Message, Tool
from skene.llm.base import LLMClient
from skene.output import DEBUG_DIR

_SESSION_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H%M%S")
_DEBUG_DIR = DEBUG_DIR


class DebugLLMClient(LLMClient):
    """Wraps any LLMClient and logs prompts and responses to a debug log file.

    Log files are written to ``~/.local/state/skene/debug/debug_<timestamp>.log``,
    one file per session (process invocation).
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._log_path = _DEBUG_DIR / f"debug_{_SESSION_TIMESTAMP}.log"
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        self._call_count = 0

        # Write session header
        self._write(
            f"=== Debug session started at {datetime.now().isoformat()} ===\n"
            f"Provider: {client.get_provider_name()}\n"
            f"Model: {client.get_model_name()}\n"
            f"Log file: {self._log_path}\n"
            f"{'=' * 60}\n"
        )
        logger.debug("Debug LLM logging enabled → {}", self._log_path)

    def _write(self, text: str) -> None:
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        self._call_count += 1
        call_id = self._call_count
        ts = datetime.now().isoformat()

        self._write(
            f"\n--- Call #{call_id} | {ts} ---\n"
            f"Provider: {self._client.get_provider_name()}\n"
            f"Model: {self._client.get_model_name()}\n"
            f"\n[PROMPT]\n{prompt}\n"
        )
        logger.debug(
            "LLM call #{} | provider={} model={} prompt_len={}",
            call_id,
            self._client.get_provider_name(),
            self._client.get_model_name(),
            len(prompt),
        )

        start = time.monotonic()
        content, usage = await self._client.generate_content_with_usage(prompt)
        duration = time.monotonic() - start

        token_info = ""
        if usage:
            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            token_info = f" | {out:,} out / {inp:,} in"
        self._write(f"\n[RESPONSE] ({duration:.2f}s{token_info})\n{content}\n\n--- End call #{call_id} ---\n")
        logger.debug(
            "LLM call #{} completed | {:.2f}s | response_len={}{}",
            call_id,
            duration,
            len(content),
            token_info,
        )
        return (content, usage)

    async def generate_content_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        self._call_count += 1
        call_id = self._call_count
        ts = datetime.now().isoformat()

        self._write(
            f"\n--- Call #{call_id} (stream) | {ts} ---\n"
            f"Provider: {self._client.get_provider_name()}\n"
            f"Model: {self._client.get_model_name()}\n"
            f"\n[PROMPT]\n{prompt}\n"
        )
        logger.debug(
            "LLM stream #{} | provider={} model={} prompt_len={}",
            call_id,
            self._client.get_provider_name(),
            self._client.get_model_name(),
            len(prompt),
        )

        start = time.monotonic()
        chunks: list[str] = []
        async for chunk in self._client.generate_content_stream(prompt):
            chunks.append(chunk)
            yield chunk
        duration = time.monotonic() - start

        full_response = "".join(chunks)
        self._write(f"\n[RESPONSE] (stream, {duration:.2f}s)\n{full_response}\n\n--- End call #{call_id} ---\n")
        logger.debug(
            "LLM stream #{} completed | {:.2f}s | response_len={}",
            call_id,
            duration,
            len(full_response),
        )

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
    ) -> AssistantTurn:
        self._call_count += 1
        call_id = self._call_count
        ts = datetime.now().isoformat()

        tool_names = ", ".join(t.name for t in tools) or "(none)"
        msg_summary = _summarize_messages(messages)
        self._write(
            f"\n--- Call #{call_id} (tools) | {ts} ---\n"
            f"Provider: {self._client.get_provider_name()}\n"
            f"Model: {self._client.get_model_name()}\n"
            f"Tools: {tool_names}\n"
            f"\n[MESSAGES]\n{msg_summary}\n"
        )
        logger.debug(
            "LLM tool call #{} | provider={} model={} messages={} tools={}",
            call_id,
            self._client.get_provider_name(),
            self._client.get_model_name(),
            len(messages),
            len(tools),
        )

        start = time.monotonic()
        turn = await self._client.generate_with_tools(messages, tools)
        duration = time.monotonic() - start

        token_info = ""
        if turn.usage:
            inp = turn.usage.get("input_tokens", 0)
            out = turn.usage.get("output_tokens", 0)
            token_info = f" | {out:,} out / {inp:,} in"
        tc_summary = ""
        if turn.tool_calls:
            tc_summary = "\n[TOOL_CALLS]\n" + "\n".join(
                f"  {tc.name}({_short_json(tc.arguments)})" for tc in turn.tool_calls
            )
        self._write(
            f"\n[RESPONSE] ({duration:.2f}s{token_info})\n"
            f"text: {turn.text!r}{tc_summary}\n"
            f"\n--- End call #{call_id} ---\n"
        )
        logger.debug(
            "LLM tool call #{} completed | {:.2f}s | tool_calls={}{}",
            call_id,
            duration,
            len(turn.tool_calls),
            token_info,
        )
        return turn

    def get_model_name(self) -> str:
        return self._client.get_model_name()

    def get_provider_name(self) -> str:
        return self._client.get_provider_name()


def _summarize_messages(messages: list[Message]) -> str:
    """Compact, log-friendly summary of a message list — full content is
    too verbose for the agent loop's many turns.
    """
    lines: list[str] = []
    for i, m in enumerate(messages):
        body = (m.content or "").strip().replace("\n", " ")
        if len(body) > 200:
            body = body[:197] + "..."
        extra = ""
        if m.tool_calls:
            extra = f" tool_calls=[{', '.join(tc.name for tc in m.tool_calls)}]"
        if m.tool_call_id:
            extra = f" tool_call_id={m.tool_call_id}"
        lines.append(f"  [{i}] {m.role}{extra}: {body}")
    return "\n".join(lines)


def _short_json(obj: object, limit: int = 160) -> str:
    import json as _json

    try:
        s = _json.dumps(obj, default=str)
    except Exception:  # noqa: BLE001
        s = str(obj)
    if len(s) > limit:
        s = s[: limit - 3] + "..."
    return s
