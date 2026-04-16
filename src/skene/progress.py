"""Shared async progress helpers for long-running LLM calls."""

from __future__ import annotations

import asyncio
from typing import Awaitable, TypeVar

from skene.output import console

T = TypeVar("T")


async def show_progress_indicator(stop_event: asyncio.Event) -> None:
    """Show a simple filled-box progress indicator until stopped."""
    count = 0
    while not stop_event.is_set():
        count += 1
        console.print("[cyan]█[/cyan]", end="")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
            break
        except asyncio.TimeoutError:
            continue

    if count > 0:
        console.print()


async def run_with_progress(awaitable: Awaitable[T]) -> T:
    """Run an awaitable while rendering the shared progress indicator."""
    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(show_progress_indicator(stop_event))
    try:
        return await awaitable
    finally:
        stop_event.set()
        try:
            await progress_task
        except Exception:
            pass
