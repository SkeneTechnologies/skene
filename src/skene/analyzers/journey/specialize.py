"""Step 0 — per-product stage specialization.

Rewrites the ``name``, ``subtitle``, ``description``, and ``examples``
fields of the seven canonical stages based on signals from the target
repo (README + manifest + landing routes). The stage **IDs** and
**order** stay fixed, so the classifier always picks from the same seven
buckets and any downstream renderer is untouched — only the surface
vocabulary becomes product-specific.

Design:
- One LLM call, no tools. Deterministic input gathering through the
  existing :class:`FsToolset` sandbox.
- Structured JSON output parsed with the shared ``parse_json`` helper and
  a closed Pydantic schema (seven named fields), so a missing stage
  raises ValidationError which the caller catches.
- Any failure → fall back to canonical :data:`STAGES`. The pipeline
  never breaks because of this step.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from skene.analyzers._journey_common import parse_json
from skene.analyzers.journey.stages import STAGES, StageDef, stages_as_prompt
from skene.analyzers.journey.tools.fs_tools import FsToolset
from skene.llm.base import LLMClient
from skene.output import debug, status, warning


class StageSpecialization(BaseModel):
    name: str = Field(min_length=1)
    subtitle: str = Field(min_length=1)
    description: str = Field(min_length=1)
    examples: list[str] = Field(min_length=2, max_length=6)


class SpecializedStages(BaseModel):
    """Closed schema — exactly seven named fields, one per canonical id.

    Using named fields (not a dict) means a missing stage raises
    ValidationError at decode time, which the caller catches to fall
    back to canonical.
    """

    discovery: StageSpecialization
    onboarding: StageSpecialization
    activation: StageSpecialization
    engagement: StageSpecialization
    retention: StageSpecialization
    expansion: StageSpecialization
    virality: StageSpecialization

    def to_stage_defs(self, canonical: tuple[StageDef, ...] = STAGES) -> tuple[StageDef, ...]:
        """Overlay specialized fields onto canonical id/order."""
        out: list[StageDef] = []
        for s in canonical:
            spec: StageSpecialization = getattr(self, s.id)
            out.append(
                StageDef(
                    id=s.id,
                    order=s.order,
                    name=spec.name,
                    subtitle=spec.subtitle,
                    description=spec.description,
                    examples=list(spec.examples),
                )
            )
        return tuple(out)


_README_CANDIDATES = ("README.md", "README.rst", "readme.md", "Readme.md")
_ROUTE_CANDIDATES = (
    "app/page.tsx",
    "app/page.jsx",
    "app/page.js",
    "app/layout.tsx",
    "src/app/page.tsx",
    "pages/index.tsx",
    "pages/index.jsx",
    "pages/index.js",
    "public/index.html",
)


def gather_signals(repo_root: Path, max_bytes: int = 8000) -> dict[str, str]:
    """Read README / manifest / marketing-route files, truncating each.

    Each slot returns the empty string if no candidate file exists. The
    :class:`FsToolset` is used purely for its path sandbox — no agent
    drives this gather step.
    """
    ts = FsToolset(repo_root, collector=[])

    readme = ""
    for cand in _README_CANDIDATES:
        out = ts._read_file(cand, max_bytes=max_bytes)
        if isinstance(out, str):
            readme = out
            break

    manifest = _gather_manifest(ts, max_bytes=max_bytes)

    routes: list[str] = []
    bytes_left = max_bytes
    for cand in _ROUTE_CANDIDATES:
        if bytes_left <= 0 or len(routes) >= 3:
            break
        out = ts._read_file(cand, max_bytes=min(2000, bytes_left))
        if isinstance(out, str):
            routes.append(f"--- {cand} ---\n{out}")
            bytes_left -= len(out)

    return {
        "readme": readme,
        "manifest": manifest,
        "routes": "\n\n".join(routes),
    }


def _gather_manifest(ts: FsToolset, max_bytes: int) -> str:
    """Pull product-identifying fields from a JS/Python/Rust/Go manifest."""
    out = ts._read_file("package.json", max_bytes=max_bytes)
    if isinstance(out, str):
        try:
            data = json.loads(out)
            keep = {k: data.get(k) for k in ("name", "description", "homepage", "keywords") if data.get(k)}
            if keep:
                return "package.json: " + json.dumps(keep, indent=2)
        except json.JSONDecodeError:
            pass  # malformed manifest — fall through to the next one

    out = ts._read_file("pyproject.toml", max_bytes=max_bytes)
    if isinstance(out, str):
        try:
            data = tomllib.loads(out)
            proj = data.get("project", {})
            keep = {k: proj.get(k) for k in ("name", "description", "keywords") if proj.get(k)}
            if keep:
                return "pyproject.toml: " + json.dumps(keep, indent=2)
        except (tomllib.TOMLDecodeError, AttributeError):
            pass  # malformed manifest — fall through to the next one

    out = ts._read_file("Cargo.toml", max_bytes=max_bytes)
    if isinstance(out, str):
        try:
            data = tomllib.loads(out)
            pkg = data.get("package", {})
            keep = {k: pkg.get(k) for k in ("name", "description", "keywords") if pkg.get(k)}
            if keep:
                return "Cargo.toml: " + json.dumps(keep, indent=2)
        except tomllib.TOMLDecodeError:
            pass  # malformed manifest — fall through to the next one

    out = ts._read_file("go.mod", max_bytes=max_bytes)
    if isinstance(out, str):
        first = out.splitlines()[0] if out else ""
        if first.startswith("module "):
            return f"go.mod: {first}"

    return ""


SPECIALIZE_INSTRUCTIONS = """\
You specialize the seven canonical user-journey stages for a specific
product. Your job is to make each stage's vocabulary and examples
resonate with this product's domain.

Reference stage semantics (do NOT change what each stage means — only
the surface vocabulary, naming, and examples should change):
{canonical}

For each of the seven stages return:
- name: a short product-specific title (e.g. "First Estimate" instead of
  "Activation"). Keep it 1-3 words.
- subtitle: a 2-5 word evocative tagline (e.g. "From signup to first AI
  output").
- description: 1-2 sentences anchored in this product's domain. Stage
  semantics must stay identical — discovery is still "first contact +
  signup", activation is still "first real value", etc.
- examples: 3-5 product-specific milestone names that would belong in
  this stage. Use the actual nouns/verbs from this product (e.g. for an
  AI-estimate product: "First Estimate Generated", not "First Value
  Delivered"). If you cannot identify a clear example for a stage,
  reuse a canonical example.

Rules:
- Output every stage. Do not omit any.
- Do not change stage IDs (they are fixed by the schema).
- Keep stage *semantics* identical to the canonical descriptions above.
- If product context is thin, lean closer to the canonical wording
  rather than inventing.

Return ONLY a JSON object with this exact shape, no prose, no markdown,
no code fences:
{{
  "discovery":   {{"name": "...", "subtitle": "...", "description": "...", "examples": ["...", "..."]}},
  "onboarding":  {{"name": "...", "subtitle": "...", "description": "...", "examples": ["...", "..."]}},
  "activation":  {{"name": "...", "subtitle": "...", "description": "...", "examples": ["...", "..."]}},
  "engagement":  {{"name": "...", "subtitle": "...", "description": "...", "examples": ["...", "..."]}},
  "retention":   {{"name": "...", "subtitle": "...", "description": "...", "examples": ["...", "..."]}},
  "expansion":   {{"name": "...", "subtitle": "...", "description": "...", "examples": ["...", "..."]}},
  "virality":    {{"name": "...", "subtitle": "...", "description": "...", "examples": ["...", "..."]}}
}}
"""


_INPUT_TEMPLATE = """\
Product: {product_name}

--- README ---
{readme}

--- Manifest ---
{manifest}

--- Marketing routes ---
{routes}
"""


def _build_instructions() -> str:
    return SPECIALIZE_INSTRUCTIONS.format(canonical=stages_as_prompt(STAGES))


def _format_input(product_name: str, signals: dict[str, str]) -> str:
    return _INPUT_TEMPLATE.format(
        product_name=product_name,
        readme=signals.get("readme") or "(no README found)",
        manifest=signals.get("manifest") or "(no manifest found)",
        routes=signals.get("routes") or "(no marketing routes found)",
    )


async def specialize_stages(
    repo_root: Path,
    product_name: str,
    llm: LLMClient,
) -> tuple[StageDef, ...]:
    """Run the specialization step. Returns specialized stages on success,
    falls back to canonical :data:`STAGES` on any failure.
    """
    status(f"Step 0: specializing stages for product={product_name}")
    try:
        signals = gather_signals(repo_root)
    except Exception as e:  # noqa: BLE001
        warning(f"specialize: signal gather failed: {e} — falling back to canonical")
        return STAGES

    debug(
        f"specialize signals gathered: readme={len(signals['readme'])} bytes "
        f"manifest={len(signals['manifest'])} bytes "
        f"routes={len(signals['routes'])} bytes"
    )

    prompt = _build_instructions() + "\n\n" + _format_input(product_name, signals)
    try:
        response = await llm.generate_content(prompt)
    except Exception as e:  # noqa: BLE001
        warning(f"specialize: LLM call failed: {e} — falling back to canonical")
        return STAGES

    parsed = parse_json(response)
    if parsed is None:
        warning("specialize: non-JSON response — falling back to canonical")
        return STAGES

    try:
        coerced = SpecializedStages.model_validate(parsed)
    except ValidationError as e:
        warning(f"specialize: invalid result: {e} — falling back to canonical")
        return STAGES

    specialized = coerced.to_stage_defs(STAGES)
    status("Step 0: stage specialization complete — names=[" + ", ".join(s.name for s in specialized) + "]")
    return specialized
