"""LLM code agent — the agentic extractor, mirroring skene/skene's code agent.

Walks the repo through fs-tools and emits candidate milestones via ``emit_milestone``.
Implements the ``CandidateExtractor`` seam, so it is a drop-in for ``HeuristicCodeScanner``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .agent_loop import run_agent
from .candidate import CandidateMilestone
from .fs_tools import FsTools
from .llm import LLMClient, LlmAnalysisError

logger = logging.getLogger("skened.pipeline.code_agent")

CODE_AGENT_INSTRUCTIONS = r"""You explore a codebase and emit candidate user-journey milestones. Be THOROUGH — err
on the side of MORE milestones, not fewer. A later step deduplicates, classifies, and
discards noise. Your job is recall.

A milestone is a meaningful user action with evidence in code:
- Public marketing pages, signup / login / OAuth / SSO / magic-link handlers.
- Settings, profile, integration, api-key endpoints.
- Each distinct domain-object creation endpoint (POST /estimates, POST /leads, ...).
- Analytics calls (track, capture, logEvent, posthog.*, mixpanel.*, segment.*) — each
  unique event name is at least one milestone; the event name is strong evidence.
- Email/SMS/push sends, queue jobs, cron handlers.
- Billing webhooks, subscription/plan changes.
- Referral, invite, share-link, public-link endpoints.

Process:
1. list_directory at the root to learn the layout.
2. Find routing files: pages/, app/, routes/, api/, src/api/, server/, controllers/.
3. search_files for analytics: "track\(", "capture\(", "posthog\.", "mixpanel\.".
4. search_files for email/queue/cron and for billing/webhooks ("stripe|webhook|subscription").
5. read_file promising hits and emit_milestone for each user-facing action.

Rules:
- Do NOT classify into stages — that is a later step.
- Use lowercase snake_case for proposed_id.
- evidence path must be a real file you read or matched.
- When you have emitted every milestone you can justify, reply with a short text summary
  (no tool call) and stop.
"""


class LlmCodeAgent:
    def __init__(self, llm: LLMClient, max_turns: int = 40) -> None:
        self._llm = llm
        self._max_turns = max_turns

    async def extract(
        self, repo_root: Path, only_paths: set[str] | None = None
    ) -> list[CandidateMilestone]:
        collector: list[CandidateMilestone] = []
        tools = FsTools(Path(repo_root), collector).as_tools()
        initial = "Begin exploring the repo. Emit one milestone per user action."
        if only_paths:
            initial += " Focus especially on these changed files: " + ", ".join(sorted(only_paths))
        try:
            turns = await run_agent(
                self._llm,
                system=CODE_AGENT_INSTRUCTIONS,
                tools=tools,
                initial_input=initial,
                max_turns=self._max_turns,
            )
        except Exception as e:  # noqa: BLE001 — a hard LLM failure must fail the run
            raise LlmAnalysisError(f"LLM code agent failed: {e}") from e
        logger.info("code agent emitted %d candidate(s) in %d turn(s)", len(collector), turns)
        return collector
