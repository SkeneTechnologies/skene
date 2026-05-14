"""
Base class for OpenAI-compatible LLM providers.

This module provides a common implementation for providers that use
the OpenAI API protocol (OpenAI, LM Studio, Ollama, and generic endpoints).
"""

import json
from typing import Any, AsyncGenerator, Optional

from pydantic import SecretStr

from skene.llm.agent_loop import AssistantTurn, Message, Tool, ToolCall
from skene.llm.base import LLMClient

DEFAULT_TIMEOUT = 900.0


class OpenAICompatibleClient(LLMClient):
    """
    Base class for OpenAI-compatible LLM clients.

    Provides common implementation for providers that use the OpenAI API protocol.
    Subclasses should set provider-specific defaults and override get_provider_name().

    Example:
        class MyClient(OpenAICompatibleClient):
            def get_provider_name(self) -> str:
                return "my-provider"
    """

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str,
        base_url: Optional[str] = None,
        default_api_key: str = "not-required",
    ):
        """
        Initialize the OpenAI-compatible client.

        Args:
            api_key: API key for the service (wrapped in SecretStr for security)
            model_name: Model name to use
            base_url: Base URL for the API endpoint. If None, uses OpenAI's default.
            default_api_key: Default API key to use if none provided (for local services)
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAI-compatible providers. Install with: pip install skene[openai]"
            )

        self.model_name = model_name
        self.base_url = base_url

        # Use provided API key or fall back to default
        api_key_value = api_key.get_secret_value() if api_key else default_api_key

        # Build client kwargs
        client_kwargs = {"api_key": api_key_value}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(timeout=DEFAULT_TIMEOUT, **client_kwargs)

    async def generate_content_with_usage(
        self,
        prompt: str,
    ) -> tuple[str, dict[str, int] | None]:
        """Generate text and return (content, usage). Usage has output_tokens, input_tokens.
        Returns None when not in response."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content.strip()
            usage = getattr(response, "usage", None)
            if usage and hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
                return (content, {"output_tokens": usage.completion_tokens, "input_tokens": usage.prompt_tokens})
            return (content, None)
        except Exception as e:
            raise RuntimeError(f"Error calling {self.get_provider_name()}: {e}")

    async def generate_content_stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming.

        Args:
            prompt: The prompt to send to the model

        Yields:
            Text chunks as they are generated

        Raises:
            RuntimeError: If streaming fails
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise RuntimeError(f"Error in {self.get_provider_name()} streaming generation: {e}")

    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model_name

    def get_provider_name(self) -> str:
        """Return the provider name. Subclasses should override this."""
        return "openai-compatible"

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
    ) -> AssistantTurn:
        """One tool-use turn against an OpenAI-compatible chat-completions endpoint.

        Translates the unified message/tool representation into the
        OpenAI ``tools=`` / ``tool_choice="auto"`` API. Local-model
        endpoints (LM Studio, Ollama) accept the same shape, so this
        method covers the whole openai_compat family.
        """
        try:
            api_messages = [_to_openai_message(m) for m in messages]
            api_tools = [_tool_to_openai(t) for t in tools]
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=api_messages,
                tools=api_tools or None,
                tool_choice="auto" if api_tools else None,
            )
        except Exception as e:
            raise RuntimeError(
                f"Error calling {self.get_provider_name()} with tools: {e}"
            ) from e

        choice = response.choices[0].message
        text = (choice.content or "").strip() or None
        tool_calls: list[ToolCall] = []
        for raw_tc in getattr(choice, "tool_calls", None) or []:
            try:
                args = json.loads(raw_tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": raw_tc.function.arguments}
            tool_calls.append(
                ToolCall(id=raw_tc.id, name=raw_tc.function.name, arguments=args)
            )

        usage = getattr(response, "usage", None)
        usage_dict: dict[str, int] | None = None
        if usage and hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
            usage_dict = {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
            }

        return AssistantTurn(text=text, tool_calls=tool_calls, usage=usage_dict, raw=response)


def _to_openai_message(m: Message) -> dict[str, Any]:
    """Translate a unified :class:`Message` into OpenAI chat-completions shape."""
    if m.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": m.tool_call_id or "",
            "content": m.content or "",
        }
    if m.role == "assistant":
        out: dict[str, Any] = {"role": "assistant", "content": m.content}
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ]
        return out
    # system / user
    return {"role": m.role, "content": m.content or ""}


def _tool_to_openai(t: Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        },
    }
