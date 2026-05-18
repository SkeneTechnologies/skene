"""
Abstract base class for LLM clients.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from skene.llm.agent_loop import AgentRunResult, AssistantTurn, Message, Tool


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.

    Provides a unified interface to interact with different LLM providers.
    Implementations should handle provider-specific details internally.

    Subclasses must implement ``generate_content_with_usage``,
    ``generate_content_stream``, ``get_model_name``, and ``get_provider_name``.
    They may also override ``generate_with_tools`` to enable tool-use
    (agent) workflows; the default raises ``NotImplementedError`` so
    providers without native tool support fail loudly when an agent
    workflow is attempted.

    Example:
        client = create_llm_client("gemini", api_key, "gemini-3-flash-preview")
        response = await client.generate_content("Hello, world!")
    """

    @abstractmethod
    async def generate_content_with_usage(self, prompt: str) -> tuple[str, dict[str, int] | None]:
        """Generate content and return (content, usage_dict).

        Usage dict has ``output_tokens`` and ``input_tokens`` keys.
        Return ``None`` for usage when the provider doesn't expose token counts.
        """
        pass

    async def generate_content(self, prompt: str) -> str:
        """Generate text from the LLM (convenience wrapper that discards usage)."""
        content, _ = await self.generate_content_with_usage(prompt)
        return content

    @abstractmethod
    async def generate_content_stream(
        self,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate text from the LLM with streaming.

        Args:
            prompt: User input or message content

        Yields:
            Text chunks as they are generated
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the name of the underlying model."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'google', 'openai')."""
        pass

    async def generate_with_tools(
        self,
        messages: "list[Message]",
        tools: "list[Tool]",
    ) -> "AssistantTurn":
        """Run a single tool-use turn against the model.

        Each provider translates the unified :class:`Message` and
        :class:`Tool` representations into its native tool-calling API and
        returns the model's response normalized into an
        :class:`AssistantTurn`. The default implementation raises so
        providers without tool support fail loudly.
        """
        raise NotImplementedError(f"{self.get_provider_name()} does not implement generate_with_tools yet")

    async def run_agent(
        self,
        instructions: str,
        tools: "list[Tool]",
        initial_input: str,
        max_turns: int = 20,
    ) -> "AgentRunResult":
        """Run an agent loop, dispatching tool calls until the model stops.

        Default implementation delegates to
        :func:`skene.llm.agent_loop.run_agent`. Providers may override
        this if they need different semantics, but they should generally
        only override :meth:`generate_with_tools`.
        """
        from skene.llm.agent_loop import run_agent

        return await run_agent(
            self,
            instructions=instructions,
            tools=tools,
            initial_input=initial_input,
            max_turns=max_turns,
        )
