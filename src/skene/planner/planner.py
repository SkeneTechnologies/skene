"""
Plan generator.

Creates detailed implementation plans for growth strategies.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from skene.llm import LLMClient
from skene.output import debug, status
from skene.planner._json import parse_json_fragment
from skene.planner.schema import (
    GrowthPlan,
    PlanSection,
    TechnicalExecution,
    render_plan_to_markdown,
)
from skene.planner.steps import DEFAULT_PLAN_STEPS, PlanStepDefinition

_COUNCIL_ROLE = """\
Role: You are the Council of Growth Engineers. You do not "suggest" tactics; you architect \
systems of high utility that can lead to compounding leverage from utility. You operate at \
the intersection of product architecture, data science, and behavioral psychology. Your goal \
is not "growth" — it is to engineer plans to improve product features for usability.

## The Ethos

- **Assume 99th-Percentile Competence:** No beginner definitions.
- **No "Top 10" listicles.**
- **Ruthless Selection:** If a strategy is "mid" or linear, kill it. But it still has to be \
relevant for the utility aspect that drives compounding.
- **Zero Fluff:** Every word must increase the signal-to-noise ratio.
- **Critical:** Be very thoughtful of your own thinking. Is the context provided showcasing \
some clear utility? What is it? Identify that. Now build the compounding from the angle of \
that utility or utilities.

**Never end with a question or offer help on the next step.**"""


class Planner:
    """
    Generates growth implementation plans.

    Example:
        planner = Planner()
        markdown, plan = await planner.generate_growth_plan(
            llm=llm,
            manifest_data=manifest_data,
            template_data=template_data,
        )
    """

    async def generate_growth_plan(
        self,
        llm: LLMClient,
        manifest_data: dict[str, Any],
        template_data: dict[str, Any] | None = None,
        engine_summary: str | None = None,
        user_prompt: str | None = None,
        plan_steps: list[PlanStepDefinition] | None = None,
        on_step: Callable[[int, str, str, dict[str, int] | None], None] | None = None,
        project_name_from_file: str | None = None,
    ) -> tuple[str, GrowthPlan]:
        """
        Generate a growth plan using multi-step orchestration.

        Generates Executive Summary, dynamic middle sections (from plan_steps or
        DEFAULT_PLAN_STEPS), and Technical Execution in separate LLM calls. Each
        section calls on_step when complete.

        Args:
            llm: LLM client for generation
            manifest_data: Project manifest data
            template_data: Growth template data with lifecycle stages (optional)
            engine_summary: Summary of current engine subjects/features (optional)
            user_prompt: Additional user context (optional)
            plan_steps: Step definitions for middle sections; defaults to DEFAULT_PLAN_STEPS
            on_step: Callback invoked after each section with (step_number, title, markdown, usage)
            project_name_from_file: Project name from manifest file (None = omit from markdown header)

        Returns:
            Tuple of (markdown content, validated GrowthPlan)
        """
        status("Preparing growth plan...")
        steps = plan_steps if plan_steps is not None else DEFAULT_PLAN_STEPS
        current_time_str = datetime.now().isoformat()

        shared_context = self._build_shared_context(
            manifest_data=manifest_data,
            template_data=template_data,
            engine_summary=engine_summary,
            user_prompt=user_prompt,
            current_time_str=current_time_str,
        )

        accumulated: list[str] = []

        # Step 1: Executive Summary (disabled)
        # exec_summary, exec_tokens = await self._generate_executive_summary(llm, shared_context)
        exec_summary = ""
        # exec_md = f"## Executive Summary\n\n{exec_summary}\n"
        # accumulated.append(exec_md)
        # if on_step:
        #     on_step(1, "Executive Summary", exec_md, exec_tokens)

        # Steps 2..N: Dynamic sections from step definitions
        raw_sections: list[PlanSection] = []
        for i, step in enumerate(steps, start=1):
            content, section_tokens = await self._generate_section(llm, shared_context, step, accumulated)
            section = PlanSection(title=step.title, content=content)
            raw_sections.append(section)
            section_md = f"### {i}. {step.title}\n\n{content}\n"
            accumulated.append(section_md)
            if on_step:
                on_step(i, step.title, section_md, section_tokens)

        # Final step: Technical Execution
        # section_index: 1-based position among numbered plan sections
        # callback_step: 1-based position across all LLM calls (1..N=sections, N+1=TE)
        section_index = len(raw_sections) + 1
        llm_call_count = len(steps) + 1
        tech_exec, te_tokens = await self._generate_technical_execution(llm, shared_context, accumulated)
        te_md = (
            f"### {section_index}. Technical Execution\n\n"
            f"**Overview**\n{tech_exec.overview}\n\n"
            f"**What We're Building**\n{tech_exec.what_we_building}\n\n"
            f"**Technical Tasks**\n{tech_exec.tasks}\n\n"
            f"**Data Triggers**\n{tech_exec.data_triggers}\n\n"
            f"**Success Metrics**\n{tech_exec.success_metrics}\n"
        )
        accumulated.append(te_md)
        if on_step:
            on_step(llm_call_count, "Technical Execution", te_md, te_tokens)

        plan = GrowthPlan(
            executive_summary=exec_summary,
            sections=raw_sections,
            technical_execution=tech_exec,
        )
        markdown = render_plan_to_markdown(plan, current_time_str, project_name_from_file)
        return markdown, plan

    # ------------------------------------------------------------------
    # Per-step generators
    # ------------------------------------------------------------------

    async def _generate_executive_summary(
        self,
        llm: LLMClient,
        shared_context: str,
    ) -> tuple[str, dict[str, int] | None]:
        prompt = (
            f"{_COUNCIL_ROLE}\n\n"
            f"## Project Context\n\n{shared_context}\n\n"
            "---\n\n"
            "## Task: Executive Summary\n\n"
            "Write the Executive Summary for this growth plan in 2-3 sentences maximum. "
            "Apply the Growth Core framework: strip the input to fundamental analysis, identify "
            "the Global Maximum (ignoring local maxima), and state the single highest-leverage "
            "utility that drives compounding.\n\n"
            "Return ONLY a JSON object with one field:\n"
            '{"executive_summary": "<string>"}\n\n'
            "No markdown fences, no explanation."
        )
        response, tokens = await llm.generate_content_with_usage(prompt)
        data = parse_json_fragment(response)
        return (str(data.get("executive_summary", response.strip())), tokens)

    async def _generate_section(
        self,
        llm: LLMClient,
        shared_context: str,
        step: PlanStepDefinition,
        accumulated: list[str],
    ) -> tuple[str, dict[str, int] | None]:
        prior = "\n".join(accumulated) if accumulated else ""
        prior_block = f"## Prior sections (for coherence)\n\n{prior}\n\n---\n\n" if prior else ""
        prompt = (
            f"{_COUNCIL_ROLE}\n\n"
            f"## Project Context\n\n{shared_context}\n\n"
            f"{prior_block}"
            f"## Task: {step.title}\n\n"
            f"{step.instruction}\n\n"
            "Return ONLY a JSON object with two fields:\n"
            f'{{"title": "{step.title}", "content": "<string>"}}\n\n'
            "No markdown fences, no explanation."
        )
        response, tokens = await llm.generate_content_with_usage(prompt)
        data = parse_json_fragment(response)
        return (str(data.get("content", response.strip())), tokens)

    async def _generate_technical_execution(
        self,
        llm: LLMClient,
        shared_context: str,
        accumulated: list[str],
    ) -> tuple[TechnicalExecution, dict[str, int] | None]:
        prior = "\n".join(accumulated)
        prompt = (
            f"{_COUNCIL_ROLE}\n\n"
            f"## Project Context\n\n{shared_context}\n\n"
            f"## Prior sections (for coherence)\n\n{prior}\n\n"
            "---\n\n"
            "## Task: Technical Execution\n\n"
            "Produce a focused Technical Execution blueprint. Focus ONLY on the most important "
            "technical tasks. Be very short and to-the-point. Do NOT use Now/Next/Later or any "
            "phase grouping.\n\n"
            "Structure:\n"
            "- overview: 1-2 sentences stating what we're building and confidence (e.g. '95%').\n"
            "- what_we_building: Short numbered list (3-5 items) of what we're building.\n"
            "- tasks: 3-7 most important technical tasks only. Each task: one line, action + file/path. "
            "Order by implementation dependency. No phase labels.\n"
            "- data_triggers: Brief list of events/conditions that trigger the flow.\n"
            "- success_metrics: Brief primary success metrics.\n\n"
            "Return ONLY a JSON object:\n"
            '{"overview": "<string>", "what_we_building": "<string>", "tasks": "<string>", '
            '"data_triggers": "<string>", "success_metrics": "<string>"}\n\n'
            "No markdown fences, no explanation."
        )
        response, tokens = await llm.generate_content_with_usage(prompt)
        data = parse_json_fragment(response)
        te = TechnicalExecution(
            overview=str(data.get("overview", "")),
            what_we_building=str(data.get("what_we_building", "")),
            tasks=str(data.get("tasks", "")),
            data_triggers=str(data.get("data_triggers", "")),
            success_metrics=str(data.get("success_metrics", "")),
        )
        return (te, tokens)

    def _build_shared_context(
        self,
        manifest_data: dict[str, Any],
        template_data: dict[str, Any] | None,
        engine_summary: str | None,
        user_prompt: str | None,
        current_time_str: str,
    ) -> str:
        """Build the shared context string passed to every per-step prompt."""
        manifest_summary = self._format_manifest_summary(manifest_data)

        template_section = ""
        if template_data:
            debug("Including growth template context")
            template_summary = self._format_template_summary(template_data)
            template_section = f"\n### Growth Journey (Lifecycle Template)\n{template_summary}\n"

        engine_section = ""
        if engine_summary:
            debug("Including engine context in planner prompts")
            engine_section = f"\n{engine_summary}\n"

        user_context_section = ""
        if user_prompt:
            user_context_section = f"### User Context\n{user_prompt}\n"

        mechanics_section = self._build_mechanics_section(template_data)

        return (
            f"**Current Date/Time:** {current_time_str}\n\n"
            f"### Project Manifest (Current State)\n{manifest_summary}\n"
            f"{template_section}"
            f"{engine_section}"
            f"{user_context_section}"
            f"\n### Five-Point Thinking Framework\n{mechanics_section}"
        )

    async def generate_activation_memo(
        self,
        llm: LLMClient,
        manifest_data: dict[str, Any],
        template_data: dict[str, Any] | None = None,
        engine_summary: str | None = None,
        user_prompt: str | None = None,
    ) -> str:
        """
        Generate a Value Realisation Plan memo.

        Produces a user-journey-driven activation strategy told from the
        customer's perspective — from first touch to advocacy — with
        concrete actions, risk tripwires, and health metrics.

        Args:
            llm: LLM client for generation
            manifest_data: Project manifest data
            template_data: Growth template data with lifecycle stages (optional)
            engine_summary: Summary of current engine subjects/features (optional)
            user_prompt: Additional user context (optional)

        Returns:
            Markdown content for the memo
        """
        status("Preparing activation memo...")
        # Build context for memo generation
        manifest_summary = self._format_manifest_summary(manifest_data)

        template_section = ""
        if template_data:
            debug("Including growth template context")
            template_summary = self._format_template_summary(template_data)
            template_section = f"\n### Growth Journey (Lifecycle Template)\n{template_summary}\n"

        engine_section = ""
        if engine_summary:
            debug("Including engine context in activation memo prompt")
            engine_section = f"\n{engine_summary}\n"

        # Get current machine time for date reference
        current_time = datetime.now()
        current_time_str = current_time.isoformat()

        # Build user context section (extract to avoid nested f-string with escape sequences)
        user_context_section = ""
        if user_prompt:
            user_context_section = f"### User Context\n{user_prompt}\n"

        status("Generating activation memo (this may take a moment)...")
        prompt = f"""You write internal strategy memos. Your job is to produce a Value Realisation \
Plan — a step-by-step activation strategy told from the customer's perspective as a journey.

Write it like a concise internal memo that a Head of Customer Success would hand to their team. \
No fluff, no filler. Every section should answer: "What does the customer experience right now, \
and what do we need to make happen next?"

## How to think about this

Read the project context below. Then walk through the customer's journey from the moment they \
first touch the product to the moment they would confidently recommend it to someone else. At \
each stage, identify:

1. What the customer is trying to do
2. What value they should experience
3. What could go wrong
4. What the product (or team) must do to keep them moving forward

The plan should feel like reading someone's diary of becoming a successful user — except you are \
writing it before it happens, so the team can engineer that outcome.

## Memo structure

### Opening: The One-Line Bet
One sentence. What is the core bet this product makes with every new customer? \
(Example: "We bet that if a developer sees their first PLG gap within 3 minutes, they will stay.")

### Chapter 1: Arrival (Minutes 0–10)
The customer just showed up. They have intent but zero context.
- What is the very first thing they should do?
- What should they see or feel within the first few minutes?
- What is the "proof of life" moment — the smallest signal that this product works for them?
- What kills momentum here? Name the specific friction points and how to eliminate each one.

### Chapter 2: First Win (Minutes 10–60)
The customer has oriented themselves. Now they need a reason to care.
- What is the first real outcome they can produce? Be specific — not "explore the dashboard" \
but "see three actionable findings about their own codebase."
- Why does this outcome matter to them personally (not to the business, to them)?
- What is the exact sequence of actions that gets them there?
- What does "done" look like? Describe the screen, the output, the feeling.

### Chapter 3: Building Confidence (Days 1–7)
They got one win. Now they need to trust that it was not a fluke.
- What is the second and third valuable outcome they should achieve?
- How does each outcome build on the previous one?
- Where do users typically stall at this stage and why?
- What proactive nudge (in-product or human) should happen if they go quiet?

### Chapter 4: The Habit (Days 7–30)
The customer is deciding whether this becomes part of how they work.
- What does regular, recurring usage look like for this product?
- What is the "workflow moment" — the point where the product slots into an existing routine?
- What new capabilities should they discover organically at this stage?
- What is the health signal that tells us they are on track vs. at risk?

### Chapter 5: Expansion (Days 30–90)
The customer has personal value. Now it spreads.
- How does the value extend to their team or organisation?
- What triggers the "I should show this to my colleague" moment?
- What deeper features or integrations become relevant now?
- What would make them upgrade, expand, or advocate?

### Chapter 6: Risks & Tripwires
A table of activation risks. For each risk:
- **Signal**: What you would observe (a metric, a behaviour, an absence)
- **Stage**: Which chapter it belongs to
- **Response**: The specific action to take (automated or human)

### Closing: The Scorecard
Define 5–7 health metrics across the journey. For each:
- What it measures
- Healthy benchmark
- When to check it

## Rules

- Write from the customer's point of view. Use "they" for the customer, not "you."
- Be concrete. Name actual features, commands, screens, and outputs from the project context.
- No generic advice. Every recommendation must be grounded in what this specific product does.
- No jargon. If a 10-year-old cannot understand the sentence structure, rewrite it.
- Keep it short. The entire memo should be something you can read in under 10 minutes.
- Do not suggest demos, fake data, or hardcoded heuristics. Every step must involve real \
product functionality producing real output.

---

## Context

**Date:** {current_time_str}

### Project
{manifest_summary}
{template_section}
{engine_section}
{user_context_section}
"""

        response = await llm.generate_content(prompt)
        status("Activation memo generated successfully")
        return response

    def _format_manifest_summary(self, manifest_data: dict[str, Any]) -> str:
        """Format manifest data into a readable summary."""
        lines = []

        if "project_name" in manifest_data:
            lines.append(f"**Project:** {manifest_data['project_name']}")

        if "description" in manifest_data:
            lines.append(f"**Description:** {manifest_data['description']}")

        if "tech_stack" in manifest_data:
            tech = manifest_data["tech_stack"]
            lines.append("\n**Tech Stack:**")
            for key, value in tech.items():
                if value:
                    lines.append(f"- {key}: {value}")

        if "current_growth_features" in manifest_data and manifest_data["current_growth_features"]:
            lines.append(f"\n**Existing Growth Features:** {len(manifest_data['current_growth_features'])} detected")
            for hub in manifest_data["current_growth_features"][:3]:
                lines.append(f"- {hub.get('feature_name', 'Unknown')}")

        if "growth_opportunities" in manifest_data and manifest_data["growth_opportunities"]:
            lines.append(f"\n**Growth Opportunities:** {len(manifest_data['growth_opportunities'])} identified")
            for gap in manifest_data["growth_opportunities"][:3]:
                lines.append(f"- {gap.get('feature_name', 'Unknown')} (priority: {gap.get('priority', 'N/A')})")

        return "\n".join(lines)

    @staticmethod
    def _build_mechanics_section(
        template_data: dict[str, Any] | None,
    ) -> str:
        """Build the How section from lifecycle template stages.

        Each lifecycle stage becomes a leverage point the council must
        address. Falls back to four default powers when no template is
        available.
        """
        default = (
            "4. **How? (The Mechanics of Leverage):** Detail the engineering "
            "of the move based on the four powers:\n"
            "- **Control of Onboarding:** Owning the first 60 seconds.\n"
            "- **Control of Retention:** Turning usage into a structural "
            "switching cost.\n"
            "- **Control of Virality:** Engineering the "
            '"Inherent Invite."\n'
            "- **Control of Friction:** Weaponizing or removing friction "
            "where it matters most."
        )

        if not template_data:
            return default

        lifecycles = template_data.get("lifecycles")
        if not lifecycles:
            return default

        sorted_stages = sorted(
            lifecycles,
            key=lambda lc: lc.get("order_index", 999),
        )

        lines = [
            "4. **How? (The Mechanics of Leverage):** Detail the "
            "engineering of the move across the product's lifecycle stages:"
        ]
        for lc in sorted_stages:
            name = lc.get("name", "UNKNOWN")
            desc = lc.get("description", "")
            label = f"{name} — {desc}" if desc else name
            milestones = lc.get("milestones", [])
            milestone_names = [m.get("title", "") for m in milestones[:3] if m.get("title")]
            hint = f" (key milestones: {', '.join(milestone_names)})" if milestone_names else ""
            lines.append(f"- **Control of {label}:**{hint}")

        return "\n".join(lines)

    def _format_template_summary(self, template_data: dict[str, Any]) -> str:
        """Format growth template data into a readable summary."""
        lines = []

        if "title" in template_data:
            lines.append(f"**Framework:** {template_data['title']}")

        if "description" in template_data:
            lines.append(f"**Description:** {template_data['description']}")

        if "lifecycles" in template_data and template_data["lifecycles"]:
            lines.append(f"\n**Lifecycle Stages:** {len(template_data['lifecycles'])} stages")
            for lifecycle in template_data["lifecycles"][:4]:  # Show top 4 stages
                name = lifecycle.get("name", "Unknown")
                desc = lifecycle.get("description", "")
                lines.append(f"\n**{name}:** {desc}")

                # Show key milestones
                if lifecycle.get("milestones"):
                    milestones = lifecycle["milestones"][:2]  # Top 2 milestones
                    lines.append("  Key milestones:")
                    for milestone in milestones:
                        lines.append(f"  - {milestone.get('title', 'Unknown')}")

                # Show key metrics
                if lifecycle.get("metrics"):
                    metrics = lifecycle["metrics"][:2]  # Top 2 metrics
                    lines.append("  Key metrics:")
                    for metric in metrics:
                        benchmark = metric.get("healthyBenchmark", "N/A")
                        lines.append(f"  - {metric.get('name', 'Unknown')}: {benchmark}")

        return "\n".join(lines)
