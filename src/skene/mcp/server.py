"""MCP server for skene.

This module provides an MCP server that exposes skene analysis
capabilities to AI assistants.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from skene import __version__
from skene.mcp.cache import AnalysisCache
from skene.mcp.registry import (
    ToolRunner,
    get_cache_dir,
    get_cache_ttl,
    get_tool_definitions,
    is_cache_enabled,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SkeneGrowthMCPServer:
    """MCP server for skene codebase analysis."""

    def __init__(self) -> None:
        """Initialize the server."""
        self.server = Server("skene")
        self.cache = AnalysisCache(
            cache_dir=get_cache_dir(),
            ttl=get_cache_ttl(),
        )
        self.cache_enabled = is_cache_enabled()
        self.tool_runner = ToolRunner(cache=self.cache, cache_enabled=self.cache_enabled)
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(name=tool.name, description=tool.description, inputSchema=tool.input_schema)
                for tool in get_tool_definitions()
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
            """Handle tool calls."""
            try:
                result = await self.tool_runner.call(name, arguments)

                return [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]

            except Exception as e:
                error_msg = str(e)
                return [{"type": "text", "text": f"Error: {error_msg}", "isError": True}]


async def serve() -> None:
    """Run the MCP server."""
    logger.info(f"Starting skene MCP server v{__version__}")

    server = SkeneGrowthMCPServer()

    async with stdio_server() as (read_stream, write_stream):
        await server.server.run(
            read_stream,
            write_stream,
            server.server.create_initialization_options(),
        )


def main() -> None:
    """Main entry point."""
    import asyncio

    asyncio.run(serve())


if __name__ == "__main__":
    main()
