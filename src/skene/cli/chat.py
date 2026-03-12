"""Interactive terminal chat that invokes skene tools."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from skene.llm import create_llm_client

DEFAULT_MAX_STEPS = 4
DEFAULT_TOOL_OUTPUT_LIMIT = 4000
DEFAULT_HISTORY_LIMIT = 12


@dataclass
class ChatState:
    """Conversation state for chat sessions."""

    history: list[dict[str, str]] = field(default_factory=list)


def run_chat(
    *,
    console: Console,
    repo_path: Path,
    api_key: str,
    provider: str,
    model: str,
    max_steps: int = DEFAULT_MAX_STEPS,
    tool_output_limit: int = DEFAULT_TOOL_OUTPUT_LIMIT,
    debug: bool = False,
    base_url: str | None = None,
) -> None:
    """Run the interactive chat loop."""
    # Import chat dependencies (these don't require the MCP package)
    from skene.mcp.cache import AnalysisCache
    from skene.mcp.registry import (
        ToolRunner,
        get_cache_dir,
        get_cache_ttl,
        get_tool_definitions,
        is_cache_enabled,
    )

    resolved_repo_path = repo_path.resolve()
    tool_definitions = get_tool_definitions()
    tool_lookup = {tool.name: tool for tool in tool_definitions}

    cache = AnalysisCache(cache_dir=get_cache_dir(), ttl=get_cache_ttl())
    tool_runner = ToolRunner(cache=cache, cache_enabled=is_cache_enabled())

    llm = create_llm_client(provider, SecretStr(api_key), model, base_url=base_url, debug=debug)
    state = ChatState()

    console.print(
        Panel.fit(
            f"[bold blue]Chat mode[/bold blue]\n"
            f"Repo: {resolved_repo_path}\n"
            f"Provider: {provider}\n"
            f"Model: {model}\n"
            "Commands: help, tools, reset, exit",
            title="skene",
        )
    )

    asyncio.run(
        _chat_loop(
            console=console,
            state=state,
            llm=llm,
            tool_runner=tool_runner,
            tool_definitions=tool_definitions,
            tool_lookup=tool_lookup,
            repo_path=resolved_repo_path,
            max_steps=max_steps,
            tool_output_limit=tool_output_limit,
        )
    )


async def _chat_loop(
    *,
    console: Console,
    state: ChatState,
    llm,
    tool_runner,
    tool_definitions,
    tool_lookup,
    repo_path: Path,
    max_steps: int,
    tool_output_limit: int,
) -> None:
    tool_summary = _format_tool_summary(tool_definitions)
    system_prompt = _build_system_prompt(tool_summary, repo_path)

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Exiting chat.[/dim]")
            return

        if not user_input:
            continue

        command = user_input.lower().strip()
        if command in {"exit", "quit"}:
            console.print("[dim]Exiting chat.[/dim]")
            return
        if command in {"help", "/help"}:
            _show_help(console)
            continue
        if command in {"tools", "/tools"}:
            _show_tools(console, tool_definitions)
            continue
        if command in {"reset", "/reset"}:
            state.history.clear()
            console.print("[dim]Conversation reset.[/dim]")
            continue

        response = await _handle_user_message(
            state=state,
            llm=llm,
            tool_runner=tool_runner,
            tool_lookup=tool_lookup,
            repo_path=repo_path,
            system_prompt=system_prompt,
            max_steps=max_steps,
            tool_output_limit=tool_output_limit,
            user_input=user_input,
        )
        console.print(f"\n[bold blue]Assistant[/bold blue]: {response}\n")


async def _handle_user_message(
    *,
    state: ChatState,
    llm,
    tool_runner,
    tool_lookup,
    repo_path: Path,
    system_prompt: str,
    max_steps: int,
    tool_output_limit: int,
    user_input: str,
) -> str:
    state.history.append({"role": "user", "content": user_input})

    for _ in range(max_steps):
        prompt = _build_prompt(system_prompt, state.history)
        raw_response = await llm.generate_content(prompt)
        parsed = _parse_llm_response(raw_response)

        if not isinstance(parsed, dict):
            final_message = raw_response.strip() or "I did not receive a response. Please try again."
            state.history.append({"role": "assistant", "content": final_message})
            return final_message

        if parsed.get("action") == "respond":
            message = parsed.get("message")
            final_message = (message or raw_response or "").strip()
            if not final_message:
                final_message = "I did not receive a response. Please try again."
            state.history.append({"role": "assistant", "content": final_message})
            return final_message

        if parsed.get("action") != "call_tool":
            fallback = raw_response.strip() or "I could not interpret the response."
            state.history.append({"role": "assistant", "content": fallback})
            return fallback

        tool_name = parsed.get("tool")
        if tool_name not in tool_lookup:
            error = f"Unknown tool: {tool_name}"
            state.history.append({"role": "assistant", "content": error})
            return error

        args = parsed.get("args") or {}
        tool_def = tool_lookup[tool_name]
        normalized_args = _normalize_tool_args(tool_def, args, repo_path)
        missing_args = _missing_required_args(tool_def, normalized_args)
        if missing_args:
            error = f"Missing required arguments for {tool_name}: {', '.join(missing_args)}"
            state.history.append({"role": "assistant", "content": error})
            return error

        try:
            result = await tool_runner.call(tool_name, normalized_args)
        except Exception as exc:
            error = f"Tool error ({tool_name}): {exc}"
            state.history.append({"role": "assistant", "content": error})
            return error

        tool_message = _format_tool_message(tool_name, result, tool_output_limit)
        state.history.append({"role": "tool", "content": tool_message})

    final_message = "Reached the maximum tool calls for this request. Please refine your question."
    state.history.append({"role": "assistant", "content": final_message})
    return final_message


def _build_prompt(system_prompt: str, history: list[dict[str, str]]) -> str:
    return f"{system_prompt}\n\nConversation:\n{_render_history(history)}\n\nReturn JSON only."


def _render_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(no prior messages)"

    recent = history[-DEFAULT_HISTORY_LIMIT:]
    lines: list[str] = []
    for item in recent:
        role = item.get("role", "user")
        content = item.get("content", "")
        label = {"user": "User", "assistant": "Assistant", "tool": "Tool"}.get(role, role.title())
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _parse_llm_response(text: str) -> dict[str, Any] | None:
    cleaned = _strip_code_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _build_system_prompt(tool_summary: str, repo_path: Path) -> str:
    return (
        "You are a terminal chat router for skene.\n"
        "Decide whether to call a tool or respond directly.\n"
        "Return ONLY JSON with one of these shapes:\n"
        '{"action": "call_tool", "tool": "...", "args": {...}}\n'
        '{"action": "respond", "message": "..."}\n'
        "Rules:\n"
        "- Call tools one at a time.\n"
        "- Use tools when a tool can answer or advance the request.\n"
        f"- Default args.path to {repo_path} when required.\n"
        "- Ask follow-up questions if required inputs are missing.\n\n"
        "Available tools:\n"
        f"{tool_summary}"
    )


def _format_tool_summary(tool_definitions) -> str:
    lines = []
    for tool in tool_definitions:
        schema = tool.input_schema or {}
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        optional = [name for name in properties.keys() if name not in required]
        requirements = []
        if required:
            requirements.append(f"required: {', '.join(required)}")
        if optional:
            requirements.append(f"optional: {', '.join(optional)}")
        requirement_str = f" ({'; '.join(requirements)})" if requirements else ""
        lines.append(f"- {tool.name}: {tool.description}{requirement_str}")
    return "\n".join(lines)


def _normalize_tool_args(tool_def, args: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    normalized = dict(args)
    required = set(tool_def.input_schema.get("required", []))

    if "path" in required:
        provided = normalized.get("path")
        if not provided or not Path(str(provided)).is_absolute():
            normalized["path"] = str(repo_path)
    elif "path" in normalized:
        provided = normalized["path"]
        if provided and not Path(str(provided)).is_absolute():
            normalized["path"] = str(repo_path)

    return normalized


def _missing_required_args(tool_def, args: dict[str, Any]) -> list[str]:
    required = tool_def.input_schema.get("required", [])
    return [name for name in required if name not in args]


def _format_tool_message(tool_name: str, result: dict[str, Any], limit: int) -> str:
    raw = json.dumps(result, indent=2, default=str)
    if len(raw) > limit:
        trimmed = raw[:limit]
        return f"{tool_name} result (truncated):\n{trimmed}\n... (truncated, {len(raw)} chars total)"
    return f"{tool_name} result:\n{raw}"


def _show_help(console: Console) -> None:
    console.print(
        Panel.fit(
            "Commands:\n"
            "- help: show this message\n"
            "- tools: list available tools\n"
            "- reset: clear conversation history\n"
            "- exit: leave chat",
            title="Chat Help",
        )
    )


def _show_tools(console: Console, tool_definitions) -> None:
    table = Table(title="Available Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Description", style="white")

    for tool in tool_definitions:
        table.add_row(tool.name, _shorten_description(tool.description))

    console.print(table)


def _shorten_description(text: str) -> str:
    sentence_end = text.find(". ")
    if sentence_end != -1:
        return text[: sentence_end + 1]
    return text
