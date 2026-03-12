"""
Debug wrapper for LLM clients that logs all input/output to files.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from loguru import logger

from skene.llm.base import LLMClient

_SESSION_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H%M%S")
_DEBUG_DIR = Path(".skene") / "debug"


class DebugLLMClient(LLMClient):
    """Wraps any LLMClient and logs prompts and responses to a debug log file.

    Log files are written to ``.skene/debug/debug_<timestamp>.log``,
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

    async def generate_content(self, prompt: str) -> str:
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
        response = await self._client.generate_content(prompt)
        duration = time.monotonic() - start

        self._write(f"\n[RESPONSE] ({duration:.2f}s)\n{response}\n\n--- End call #{call_id} ---\n")
        logger.debug(
            "LLM call #{} completed | {:.2f}s | response_len={}",
            call_id,
            duration,
            len(response),
        )
        return response

    async def generate_content_with_usage(self, prompt: str) -> tuple[str, int | None]:
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

    def get_model_name(self) -> str:
        return self._client.get_model_name()

    def get_provider_name(self) -> str:
        return self._client.get_provider_name()
