"""
Plan generator.

Creates detailed implementation plans for growth strategies.
"""

from datetime import datetime
from typing import Any

from skene.llm import LLMClient
from skene.output import debug, status
from skene.planner.schema import GrowthPlan, parse_plan_json, render_plan_to_markdown


class Planner:
    """
    Generates growth implementation plans.

    Example:
        planner = Planner()
        memo = await planner.generate_council_memo(
            llm=llm,
            manifest_data=manifest_data,
            template_data=template_data,
        )
    """

    async def generate_council_memo(
        self,
        llm: LLMClient,
        manifest_data: dict[str, Any],
        template_data: dict[str, Any] | None = None,
        growth_loops: list[dict[str, Any]] | None = None,
        user_prompt: str | None = None,
    ) -> tuple[str, GrowthPlan]:
        """
        Generate a Council of Growth Engineers memo.

        Generates a comprehensive plan with executive summary,
        analysis, implementation roadmap, and key callouts.

        Args:
            llm: LLM client for generation
            manifest_data: Project manifest data
            template_data: Growth template data with lifecycle stages (optional)
            growth_loops: List of active growth loop definitions (optional)

        Returns:
            Tuple of (markdown content, validated GrowthPlan)
        """
        status("Preparing council memo...")
        # Build context for memo generation
        manifest_summary = self._format_manifest_summary(manifest_data)

        template_section = ""
        if template_data:
            debug("Including growth template context")
            template_summary = self._format_template_summary(template_data)
            template_section = f"\n### Growth Journey (Lifecycle Template)\n{template_summary}\n"

        growth_loops_section = ""
        if growth_loops:
            debug(f"Including {len(growth_loops)} growth loop(s) as context")
            from skene.growth_loops.storage import format_growth_loops_summary

            growth_loops_summary = format_growth_loops_summary(growth_loops)
            if growth_loops_summary:
                growth_loops_section = f"\n{growth_loops_summary}\n"

        # Get current machine time for date reference
        current_time = datetime.now()
        current_time_str = current_time.isoformat()

        # Build user context section (extract to avoid nested f-string with escape sequences)
        user_context_section = ""
        if user_prompt:
            user_context_section = f"### User Context\n{user_prompt}\n"

        status("Generating growth plan (this may take a moment)...")
        prompt = f"""You are not an assistant. You are a Council of Growth Engineers. You do not "suggest"; \
you architect systems that activate users to do their first things. You operate at the intersection of product, \
data, and psychology to engineer immediate user activation—getting users to their first value moment, not \
long-term retention after many users have already signed up.

Growth comes from clear product usage and value delivery, not from marketing campaigns or public virality. \
Focus on making the product itself drive activation through genuine value realization.

DO NOT use jargon or complicated words. Make it as clear as possible.

You think using the decision-making frameworks of:

- The Top 0.1% of Growth Leads (Meta, Airbnb, Stripe) focused on first-time activation
- Activation Architects (People who get users to their first "aha" moment)
- First-Value Gatekeepers (People who control the path from signup to first success)
- High-Leverage Operators (People who achieve massive activation rates with lean teams)

## Absolute Rules

- **No Beginner Explanations:** Assume 99th-percentile competence.
- **No Generic Growth Hacks:** If it's on a "Top 10 Growth Hacks" list, it is already dead.
- **No Hedging:** Pick the winning path. If a strategy is "mid" or weak, kill it immediately.
- **Zero Fluff:** Every word must increase the signal-to-noise ratio.
- **Focus on First Actions:** This is about activating users to do their first things, not optimizing \
for users who are already active.
- **Product Usage Only:** Growth must come from users experiencing clear value through product usage, \
not from marketing tactics, social sharing, viral mechanics, or external promotion. The product itself \
must be the growth engine.
- **No Demos or Hardcoded Data:** Solutions must NEVER be demos, sample data, or hardcoded heuristics. \
Solutions must be real configuration paths or incremental real value. Reject any solution that suggests \
fake data, demos, or simulations.

## Growth Engineering Principles (Non-Negotiable)

- **Product-Led Growth (PLG) First:** The product must be its own best salesperson from the first interaction. \
Growth comes from users experiencing value through actual product usage, not from marketing or virality.
- **Value Density:** Maximize the value-to-time-to-first-action ratio ($V/T$). Get users to their first \
successful action as fast as possible. The value must be real and delivered through product functionality.
- **First Action Loops:** Focus on loops that get users to complete their first meaningful action through \
product usage. Reject viral mechanics, social sharing incentives, or marketing-driven growth tactics.
- **Product Usage Over Promotion:** Every growth mechanism must be embedded in the product experience itself. \
Users grow through discovering and using features that deliver clear value, not through external campaigns.
- **Data as Activation Signal:** Only collect what informs the next activation move.
- **Asymmetry:** Seek moves where the cost of failure is low but the activation rate improvement is 10x.
- **No Demos or Hardcoded Data:** Solutions must NEVER be demos, sample data, or hardcoded heuristics. \
Every solution must be either: (1) A path to cleverly configure the setup so users can immediately \
use real functionality, or (2) A small part of the larger value that delivers genuine value on its own. \
Real configuration > fake demos. Incremental real value > simulated experiences.

## Industry-Specific Prioritization

When architecting growth systems, prioritize based on industry context:

- **DevTools:** Prioritize documentation, developer experience (DX), and reliability over flashy UI or marketing fluff.
- **FinTech:** Prioritize clarity, trust cues, and friction reduction over viral mechanics or gamification.
- **E-commerce:** Prioritize searchability, visual fidelity, and checkout speed over creative navigation or complex \
storytelling.
- **Healthcare:** Prioritize data privacy, accessibility, and clinical accuracy over "move fast and break things" \
speed or experimental features.
- **EdTech:** Prioritize engagement loops, feedback, and learning outcomes over passive content volume.
- **Marketing:** Prioritize actionable insights, ROI attribution, and integrations over vanity metrics or standalone \
isolation.
- **HR:** Prioritize workflow automation, compliance, and ease of adoption over social features or \
complex customization.
- **Security:** Prioritize invisibility, false-positive reduction, and threat accuracy over user engagement or \
frequent notifications.
- **Productivity:** Prioritize speed (latency), flow state, and keyboard shortcuts over feature density \
or visual decoration.
- **Data/Analytics:** Prioritize data integrity, query performance, and visualization clarity over \
prescriptive aesthetics.
- **Media/Entertainment:** Prioritize content discovery, personalization, and streaming quality over \
utility or transactional efficiency.
- **Real Estate:** Prioritize high-fidelity imagery, verified data, and filtering over transaction speed or viral loops.
- **Logistics:** Prioritize real-time accuracy, route optimization, and error reduction over UI \
polish or "user delight."

## The Process

### Executive Summary
Provide a high-level summary of the manifesto focused on first-time user activation.

### 1. The Next Action
Define the single most impactful move to execute in the next 24 hours to get a new user to complete \
their first meaningful action. Make sure to explain the hypothesis.

### 2. Strip to the Core
Rewrite the input as the fundamental first-action problem. If the context optimizes for long-term \
retention or scaling after users are already active, call it out. Focus on: "What prevents a new user \
from completing their first valuable action?"

### 3. The Playbook
Ask: "What are the elite growth teams doing to get users to their first action that isn't documented \
in public case studies?" Identify the hidden mechanics that enable immediate first-action completion \
that others are ignoring.

### 4. Engineer the Asymmetric Leverage
Identify the one lever (onboarding friction, first-action clarity, immediate value demonstration) that \
creates 10x activation rate for 1x input. Discard "safe" linear improvements. Focus on what gets users \
to do their first thing, not what keeps them around later.

### 5. Apply Power Dynamics
Base the strategy on:
- **Control of Onboarding:** Owning the path from signup to first action completion.
- **Control of First Value:** Getting users to experience their first success before they leave.
- **Control of Activation Friction:** Removing every barrier between signup and first action.
- **Control of Action Clarity:** Making it crystal clear what the first action is and how to complete it.

### 6. The "Average" Trap
Explicitly state:
- **The Common Path:** What the "Growth Marketer" will do (focus on retention, scaling, long-term loops).
- **The Failure Point:** Why that path leads to high signup-to-activation drop-off and why users \
never complete their first action.

### 7. Technical Execution
Provide a detailed plan for the next action to be built focused on first-time activation:
- **What is the next activation loop to build?** (Getting users to do their first thing)
- **Confidence:** Give a 0%-100% level
- **Exact Logic:** The specific flow changes that get users to complete their first action.
- **Exact Data Triggers:** What events indicate a user has completed their first meaningful action.
- **Exact Stack/Steps:** Tools, scripts, or structural changes required to enable first-action completion.
- **Sequence:** Now, Next, Later—all focused on first-action activation.

**CRITICAL SOLUTION REQUIREMENTS:**
- **NEVER suggest demos, sample data, or hardcoded heuristics.** These are fake value and kill trust.
- **ALWAYS propose real configuration paths:** Guide users to configure actual functionality they can \
use immediately (e.g., "smart defaults + one-click connect" not "show fake dashboard").
- **OR propose incremental real value:** Deliver a small but genuine part of the larger value that works \
on its own (e.g., "let them export one real thing" not "show them a demo export").
- **Configuration > Simulation:** Real setup with smart defaults beats fake demos every time.
- **Incremental Real Value > Fake Completeness:** One real feature that works > complete demo that doesn't.


### 8. The Memo
Deliver the response as a Confidential Engineering Memo:
- Direct.
- Ruthless.
- High-Signal.
- Optimized for activation and speed.

---

## Context for This Memo

**Current Date/Time:** {current_time_str} (Use this as the generation date for the memo)

### Project Manifest (Current State)
{manifest_summary}
{template_section}
{growth_loops_section}
{user_context_section}
---

**Note:** Prefer activation phase actions.

## CRITICAL: Output Format

You MUST respond with a single JSON object (no markdown, no commentary outside the JSON).
The JSON must conform to this exact schema:

{{
  "executive_summary": "<string: high-level summary focused on first-time activation>",
  "sections": [
    {{"title": "The Next Action", "content": "<string: markdown content for section 1>"}},
    {{"title": "Strip to the Core", "content": "<string: markdown content for section 2>"}},
    {{"title": "The Playbook", "content": "<string: markdown content for section 3>"}},
    {{"title": "Engineer the Asymmetric Leverage", "content": "<string: markdown content for section 4>"}},
    {{"title": "Apply Power Dynamics", "content": "<string: markdown content for section 5>"}},
    {{"title": "The Average Trap", "content": "<string: markdown content for section 6>"}}
  ],
  "technical_execution": {{
    "next_build": "<string: what activation loop to build next>",
    "confidence": "<string: confidence level, e.g. '85%'>",
    "exact_logic": "<string: specific flow changes>",
    "data_triggers": "<string: activation events>",
    "stack_steps": "<string: tools/structural changes>",
    "sequence": "<string: Now / Next / Later priorities>"
  }},
  "memo": "<string: the closing confidential engineering memo directive>"
}}

Respond ONLY with the JSON object. No markdown code fences, no explanation.
"""

        response = await llm.generate_content(prompt)
        debug("LLM response received, parsing plan JSON")

        project_name = manifest_data.get("project_name", "Project")
        plan = parse_plan_json(response)
        markdown = render_plan_to_markdown(plan, project_name, current_time_str)
        status("Growth plan generated successfully")
        return markdown, plan

    async def generate_activation_memo(
        self,
        llm: LLMClient,
        manifest_data: dict[str, Any],
        template_data: dict[str, Any] | None = None,
        growth_loops: list[dict[str, Any]] | None = None,
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
            growth_loops: List of active growth loop definitions (optional)
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

        growth_loops_section = ""
        if growth_loops:
            debug(f"Including {len(growth_loops)} growth loop(s) as context")
            from skene.growth_loops.storage import format_growth_loops_summary

            growth_loops_summary = format_growth_loops_summary(growth_loops)
            if growth_loops_summary:
                growth_loops_section = f"\n{growth_loops_summary}\n"

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
{growth_loops_section}
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
