"""
Skene Chat Completions API client.

Endpoint: POST https://www.skene.ai/api/v1/chat/completions
Local/dev: POST http://localhost:3000/api/v1/chat/completions

Workspace is derived from the API key; no slug in the URL.
"""

import json
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

from skene.llm.base import LLMClient

DEFAULT_TIMEOUT = 900.0
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 50000
PRODUCTION_ENDPOINT = "https://www.skene.ai/api/v1/chat/completions"


class SkeneClient(LLMClient):
    """Client for Skene Chat Completions API."""

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Skene client.

        Args:
            api_key: Skene API key (workspace-scoped, wrapped in SecretStr)
            model_name: Model ID (e.g. "google/gemini-3-flash-preview" or "auto")
            base_url: Optional base URL for local/dev. Omit for production (www.skene.ai).
        """
        self.model_name = model_name
        self.api_key = api_key.get_secret_value()
        self._base_url = (base_url or "").strip().rstrip("/") if base_url else ""

    @property
    def _endpoint(self) -> str:
        """Return the chat completions endpoint URL."""
        if self._base_url:
            base = self._base_url.rstrip("/")
            if base.endswith("/api/v1/chat/completions") or base.endswith("/chat/completions"):
                return base
            if base.endswith("/api/v1"):
                return f"{base}/chat/completions"
            if base.endswith("/api"):
                return f"{base}/v1/chat/completions"

            parsed = urlparse(base)
            host = (parsed.hostname or "").lower()
            path = (parsed.path or "").rstrip("/")

            # Handle workspace URLs like https://www.skene.ai/workspace/<slug>
            if "/workspace/" in path:
                root = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                return f"{root}/api/v1/chat/completions"

            # Handle plain host URLs like https://www.skene.ai or http://localhost:3000
            if host in {"skene.ai", "www.skene.ai", "localhost", "127.0.0.1"} and not path:
                return f"{base}/api/v1/chat/completions"

            return f"{base}/chat/completions"
        return PRODUCTION_ENDPOINT

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, prompt: str, stream: bool) -> dict:
        """Build request payload for chat completions."""
        return {
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
            "model": self.model_name,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "temperature": DEFAULT_TEMPERATURE,
        }

    @staticmethod
    def _format_http_error(error: httpx.HTTPStatusError) -> str:
        """Return a concise error string with status and response body."""
        try:
            response = error.response
            content_type = (response.headers.get("content-type") or "").lower()

            body = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    body = str(payload.get("error") or payload.get("message") or payload)
                elif payload is not None:
                    body = str(payload)
            except Exception:
                body = response.text

            body = (body or "").strip()
            lower_body = body.lower()
            if "text/html" in content_type or lower_body.startswith("<!doctype html") or lower_body.startswith("<html"):
                body = "HTML error response (likely wrong base_url path)"
            elif len(body) > 320:
                body = f"{body[:320]}..."
        except Exception:
            body = ""
        return f"Error calling Skene: {error.response.status_code} {body}".strip()

    async def generate_content_with_usage(
        self,
        prompt: str,
    ) -> tuple[str, dict[str, int] | None]:
        """Generate text and return (content, usage)."""
        payload = self._build_payload(prompt, stream=False)

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    self._endpoint,
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(self._format_http_error(e)) from e
        except Exception as e:
            raise RuntimeError(f"Error calling Skene: {e}") from e

        data = response.json()
        content = self._extract_text(data)
        usage = self._extract_usage(data)
        return (content, usage)

    async def generate_content_stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Generate content with SSE streaming."""
        payload = self._build_payload(prompt, stream=True)

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    self._endpoint,
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_part = line[6:].strip()
                            if data_part == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data_part)
                            except json.JSONDecodeError:
                                continue
                            choices = chunk.get("choices")
                            if isinstance(choices, list) and choices:
                                delta = (choices[0] or {}).get("delta") or {}
                                content = delta.get("content")
                                if isinstance(content, str):
                                    yield content
        except httpx.HTTPStatusError as e:
            raise RuntimeError(self._format_http_error(e)) from e
        except Exception as e:
            raise RuntimeError(f"Error calling Skene: {e}") from e

    def _extract_text(self, data: dict) -> str:
        """Extract content from OpenAI-compatible response."""
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] or {}
            message = first.get("message", {}) if isinstance(first, dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                return content.strip()
        raise RuntimeError("Error calling Skene: response did not include generated content")

    def _extract_usage(self, data: dict) -> dict[str, int] | None:
        """Extract token usage from response."""
        usage = data.get("usage")
        if not isinstance(usage, dict):
            return None
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            return {"output_tokens": completion_tokens, "input_tokens": prompt_tokens}
        return None

    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model_name

    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "skene"
