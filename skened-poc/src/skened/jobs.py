"""In-process async job queue with a bounded worker pool.

The queue carries run IDs; an injected ``executor`` coroutine does the actual work for a
run (the daemon service provides it). This keeps the queue free of analysis/git/storage
dependencies.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger("skened.jobs")

Executor = Callable[[str], Awaitable[None]]


class JobQueue:
    def __init__(self, executor: Executor, concurrency: int = 2) -> None:
        self._executor = executor
        self._concurrency = max(1, concurrency)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._workers = [
            asyncio.create_task(self._worker(i), name=f"skened-worker-{i}")
            for i in range(self._concurrency)
        ]
        logger.info("job queue started with %d workers", self._concurrency)

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("job queue stopped")

    def enqueue(self, run_id: str) -> None:
        self._queue.put_nowait(run_id)

    async def join(self) -> None:
        """Wait until all enqueued runs have been processed (used by tests)."""
        await self._queue.join()

    async def _worker(self, idx: int) -> None:
        # A cancel while idle propagates out of `get()` before any item is dequeued, so
        # task_done() is only reached for items actually pulled from the queue.
        while True:
            run_id = await self._queue.get()
            try:
                await self._executor(run_id)
            except Exception:  # noqa: BLE001 — executor records its own errors; this is a backstop
                logger.exception("worker %d: unhandled error processing run %s", idx, run_id)
            finally:
                self._queue.task_done()
