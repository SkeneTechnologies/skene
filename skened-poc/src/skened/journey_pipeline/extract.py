"""Candidate extraction — the "code agent" step.

The reference pipeline drives an LLM agent over fs-tools to emit candidate milestones.
This is a deterministic, offline stand-in that walks the repo and applies regex/keyword
signals matching the same priorities the agent is told to look for (signup/auth,
analytics events, email/queue/cron, billing/webhooks, referral/invite, domain-creation
routes).

``CandidateExtractor`` is the seam: swap ``HeuristicCodeScanner`` for an LLM-backed agent
(see ``llm.py``) later without touching the rest of the pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..journey import Evidence, EvidenceSource
from .candidate import CandidateMilestone

logger = logging.getLogger("skened.pipeline.extract")

IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {"node_modules", ".git", "dist", "build", ".next", "__pycache__", "venv", ".venv",
     ".turbo", "coverage", ".pytest_cache", "target", "vendor"}
)

TEXT_SUFFIXES: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".yaml", ".yml",
     ".toml", ".md", ".html", ".vue", ".svelte", ".rb", ".go", ".java", ".kt", ".rs",
     ".php", ".cs", ".sql"}
)

MAX_FILE_BYTES = 200_000
MAX_FILES_SCANNED = 4000
MAX_EVIDENCE_PER_CANDIDATE = 6
MAX_CANDIDATES = 60


class CandidateExtractor(Protocol):
    async def extract(
        self, repo_root: Path, only_paths: set[str] | None = None
    ) -> list[CandidateMilestone]: ...


# --- presence signals: one milestone per signal, evidence accumulated across files ------
@dataclass(frozen=True)
class _Signal:
    key: str           # stable proposed_id stem
    name: str
    description: str
    pattern: re.Pattern
    reason: str
    confidence: float = 0.7


_SIGNALS: tuple[_Signal, ...] = (
    _Signal("auth_signup", "Sign up / authentication",
            "Account creation, login, or auth handler — the entry into the product.",
            re.compile(r"sign[\s_-]?up|signup|sign[\s_-]?in|signin|\bregister\b|\blogin\b|log[\s_-]?in|oauth|\bsso\b|magic[\s_-]?link", re.I),
            "Auth/signup keyword found", 0.75),
    _Signal("email_notification", "Email / notification send",
            "Transactional email, SMS, or push notification dispatch.",
            re.compile(r"sendmail|nodemailer|\bresend\b|mailgun|sendgrid|postmark|ses\.send|\.send_?email\(|push\.send", re.I),
            "Email/notification send keyword found", 0.7),
    _Signal("background_job", "Background job / scheduled task",
            "Queued work, cron, or scheduled task processing user actions asynchronously.",
            re.compile(r"\benqueue\(|\.enqueue\b|\bcron\b|\bcelery\b|\bsidekiq\b|bull(?:mq)?|setinterval\(|\bschedule\(", re.I),
            "Queue/cron keyword found", 0.65),
    _Signal("billing", "Billing / subscription",
            "Payment, checkout, subscription, or billing webhook handling.",
            re.compile(r"\bstripe\b|\bpaddle\b|subscription|\bcheckout\b|\bbilling\b|\binvoice\b|webhook", re.I),
            "Billing/subscription keyword found", 0.8),
    _Signal("referral", "Referral / invite / share",
            "Referral, invite, share-link, or attribution flow that brings in new users.",
            re.compile(r"referral|\binvite\b|share[\s_-]?link|public[\s_-]?link|\baffiliate\b|utm_", re.I),
            "Referral/invite/share keyword found", 0.8),
    _Signal("settings_integration", "Settings / integration / API key",
            "Configuration, profile, integration, or API-key setup.",
            re.compile(r"\bsettings\b|\bprofile\b|integration|api[\s_-]?key|\bconnect\b|\bwebhook[\s_-]?url\b", re.I),
            "Settings/integration keyword found", 0.65),
)

# Analytics event calls: each unique event name becomes its own milestone.
_ANALYTICS_PATTERNS = (
    re.compile(r"(?:posthog|mixpanel|segment|amplitude|analytics)\.(?:track|capture|logevent)\(\s*['\"]([\w .:\-]{2,60})['\"]", re.I),
    re.compile(r"\b(?:track|capture|logevent)\(\s*['\"]([\w .:\-]{2,60})['\"]", re.I),
)

# Domain-object creation routes: POST/PUT handlers → "Create <resource>" milestones.
_ROUTE_PATTERNS = (
    re.compile(r"(?:app|router|api|server|fastify)\.(?:post|put)\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"@\w+\.(?:post|put)\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"@(?:app|router)\.route\(\s*['\"]([^'\"]+)['\"][^)]*methods=\[[^\]]*['\"](?:POST|PUT)['\"]", re.I),
)
_NEXT_POST = re.compile(r"export\s+(?:async\s+function|const)\s+(?:POST|PUT)\b", re.I)


def _slugify(text: str, fallback: str = "milestone") -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    s = re.sub(r"_+", "_", s)
    if not s:
        return fallback
    if not s[0].isalpha():
        s = "m_" + s
    return s[:60]


def _resource_from_route(path: str) -> str | None:
    segs = [s for s in re.split(r"[/]", path) if s and not s.startswith(("{", ":", "[", "$"))]
    # Drop common prefixes; take the last meaningful segment.
    segs = [s for s in segs if s.lower() not in {"api", "v1", "v2", "v3"}]
    return segs[-1] if segs else None


class HeuristicCodeScanner:
    """Deterministic, offline candidate extractor (default)."""

    async def extract(
        self, repo_root: Path, only_paths: set[str] | None = None
    ) -> list[CandidateMilestone]:
        # File IO is synchronous; run it off the event loop.
        return await asyncio.to_thread(self._scan, Path(repo_root), only_paths)

    def _scan(self, repo_root: Path, only_paths: set[str] | None = None) -> list[CandidateMilestone]:
        # Accumulators keyed by milestone identity so repeats just add evidence.
        signal_evidence: dict[str, list[Evidence]] = {}
        event_evidence: dict[str, list[Evidence]] = {}
        route_evidence: dict[str, list[Evidence]] = {}

        scanned = 0
        for file in self._iter_text_files(repo_root, only_paths):
            if scanned >= MAX_FILES_SCANNED:
                logger.info("hit MAX_FILES_SCANNED=%d; stopping scan early", MAX_FILES_SCANNED)
                break
            try:
                text = file.read_text(errors="ignore")[:MAX_FILE_BYTES]
            except OSError:
                continue
            scanned += 1
            rel = str(file.relative_to(repo_root))

            for sig in _SIGNALS:
                if sig.pattern.search(rel) or sig.pattern.search(text):
                    _append(signal_evidence, sig.key, Evidence(
                        source=EvidenceSource.code, path=rel, reason=sig.reason))

            for pat in _ANALYTICS_PATTERNS:
                for m in pat.finditer(text):
                    event = m.group(1).strip()
                    if event:
                        _append(event_evidence, event, Evidence(
                            source=EvidenceSource.code, path=rel,
                            reason=f"Analytics event '{event}' tracked here"))

            for resource in self._routes_in(file, rel, text):
                _append(route_evidence, resource, Evidence(
                    source=EvidenceSource.code, path=rel,
                    reason=f"POST/PUT handler for '{resource}'"))

        candidates = self._build(signal_evidence, event_evidence, route_evidence)
        logger.info("heuristic scan of %s: %d candidate(s) from %d file(s)",
                    repo_root, len(candidates), scanned)
        return candidates[:MAX_CANDIDATES]

    def _iter_text_files(self, root: Path, only_paths: set[str] | None = None):
        if only_paths is not None:
            # Branch-diff mode: scan just the named (repo-relative) files.
            for rel in sorted(only_paths):
                p = root / rel
                if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
                    yield p
            return
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIR_NAMES and not d.startswith(".")]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix.lower() in TEXT_SUFFIXES:
                    yield p

    def _routes_in(self, file: Path, rel: str, text: str) -> list[str]:
        resources: list[str] = []
        for pat in _ROUTE_PATTERNS:
            for m in pat.finditer(text):
                res = _resource_from_route(m.group(1))
                if res:
                    resources.append(res)
        # Next.js app-router file convention: app/.../<resource>/route.ts with a POST export.
        if file.name in {"route.ts", "route.tsx", "route.js", "route.mjs"} and _NEXT_POST.search(text):
            res = file.parent.name
            if res and res not in {"api"}:
                resources.append(res)
        return resources

    def _build(self, signals, events, routes) -> list[CandidateMilestone]:
        out: list[CandidateMilestone] = []
        sig_by_key = {s.key: s for s in _SIGNALS}

        for key, evidence in signals.items():
            sig = sig_by_key[key]
            out.append(CandidateMilestone(
                proposed_id=sig.key, name=sig.name, description=sig.description,
                evidence=evidence[:MAX_EVIDENCE_PER_CANDIDATE], confidence=sig.confidence))

        for event, evidence in events.items():
            out.append(CandidateMilestone(
                proposed_id=_slugify(f"event_{event}"),
                name=f"Analytics event: {event}",
                description=f"Tracked analytics event '{event}' — a measured user action.",
                evidence=evidence[:MAX_EVIDENCE_PER_CANDIDATE],
                tracked_event=event, confidence=0.7))

        for resource, evidence in routes.items():
            out.append(CandidateMilestone(
                proposed_id=_slugify(f"create_{resource}"),
                name=f"Create {resource}",
                description=f"Domain-object creation endpoint for '{resource}' (POST/PUT).",
                evidence=evidence[:MAX_EVIDENCE_PER_CANDIDATE], confidence=0.7))
        return out


def _append(acc: dict[str, list[Evidence]], key: str, ev: Evidence) -> None:
    bucket = acc.setdefault(key, [])
    if len(bucket) >= MAX_EVIDENCE_PER_CANDIDATE:
        return
    if any(e.path == ev.path for e in bucket):
        return
    bucket.append(ev)
