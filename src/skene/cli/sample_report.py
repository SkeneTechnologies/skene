"""Sample growth analysis report generation."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

console = Console()


def generate_sample_growth_analysis() -> str:
    """
    Generate a sample growth analysis in the style of growth-plan.md.
    This demonstrates the kind of insights available with API key configuration.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")

    report = f"""

╔═════════════════════════════════════════════════════════════════════════════╗
║                                                                             ║
║   ██████╗ ██████╗  ██████╗ ██╗    ██╗████████╗██╗  ██╗                      ║
║  ██╔════╝ ██╔══██╗██╔═══██╗██║    ██║╚══██╔══╝██║  ██║                      ║
║  ██║  ███╗██████╔╝██║   ██║██║ █╗ ██║   ██║   ███████║                      ║
║  ██║   ██║██╔══██╗██║   ██║██║███╗██║   ██║   ██╔══██║                      ║
║  ╚██████╔╝██║  ██║╚██████╔╝╚███╔███╔╝   ██║   ██║  ██║                      ║
║   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚══╝╚══╝    ╚═╝   ╚═╝  ╚═╝                      ║
║                                                                             ║
║      ██████╗ ███████╗██████╗  ██████╗ ██████╗ ████████╗                     ║
║      ██╔══██╗██╔════╝██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝                     ║
║      ██████╔╝█████╗  ██████╔╝██║   ██║██████╔╝   ██║                        ║
║      ██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║██╔══██╗   ██║                        ║
║      ██║  ██║███████╗██║     ╚██████╔╝██║  ██║   ██║                        ║
║      ╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝                        ║
║                                                                             ║
║                           ▼ SAMPLE PREVIEW ▼                                ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝

**CONFIDENTIAL ENGINEERING MEMO**
**TO:** Engineering & Product Leadership
**FROM:** Skene Growth Intelligence
**DATE:** {timestamp}
**SUBJECT:** Unlock Full AI-Powered Growth Infrastructure for Your Codebase

───────────────────────────────────────────────────────────────────────────────

### EXECUTIVE SUMMARY

Growth infrastructure is the engineering layer that injects growth without manual
intervention. It's not marketing—it's architecting viral loops, activation
triggers, and retention mechanics directly into your codebase. Elite products (Slack,
Notion, Figma) don't grow through ads; they grow through engineered network effects,
frictionless onboarding, and compounding user value. This analysis detects where your
code creates growth opportunities and where it creates friction. To unlock the full
AI-powered analysis of YOUR codebase's growth infrastructure, run `skene config` to
get started (2 minutes).

───────────────────────────────────────────────────────────────────────────────

### 1. THE CEO'S NEXT ACTION

**Hypothesis:** The barrier between you and exponential growth insights is a 2-minute
API key setup. Every day without Skene Growth is a day of missed optimization
opportunities.

**The Action:** Run `skene config` in your terminal. This interactive setup will
guide you through:
1. Selecting your preferred LLM provider (Gemini, Anthropic, OpenAI)
2. Creating an API key (we'll provide direct links)
3. Saving your configuration securely

After setup, run `skene analyze .` to get your complete growth analysis.

───────────────────────────────────────────────────────────────────────────────

### 2. STRIP TO THE GROWTH CORE

The fundamental problem is **Feature Accumulation Fallacy**.
Most teams believe more features = more growth. This is false. Growth comes from
helping customers achieve their desired outcome faster, not from giving them more
options. Every feature adds cognitive load. Every configuration step increases
friction. The products that win are the ones that eliminate steps, not add them.

Growth is not about committing code to a codebase and then not looking at the data.
It's about instrumenting your product, measuring what actually drives customer
success, and iterating based on evidence—not assumptions. You can't optimize what
you don't measure.

**Current Core:** Building features customers might want.
**Optimal Core:** Engineering the fastest path to customer success, measured and
optimized continuously.

───────────────────────────────────────────────────────────────────────────────

### 3. THE PLAYBOOK: GET YOUR API KEY

Elite growth teams don't wait. Here's how to get started:

**Option 1: Gemini (Recommended - Fast & Free tier available)**
*   Link: https://aistudio.google.com/apikey
*   Why: 2M token context, fast, generous free tier
*   Setup time: 60 seconds

**Option 2: Anthropic Claude (Best quality)**
*   Link: https://console.anthropic.com/
*   Why: Superior reasoning, detailed analysis
*   Setup time: 90 seconds

**Option 3: OpenAI (Industry standard)**
*   Link: https://platform.openai.com/api-keys
*   Why: Reliable, well-documented
*   Setup time: 90 seconds

───────────────────────────────────────────────────────────────────────────────

### 4. ENGINEER THE ASYMMETRIC LEVERAGE

**Lever:** Automated Growth Loops with Skene

Most teams build growth features manually, one at a time. This is linear effort for
linear results. Skene automates the detection, implementation, and optimization of
growth infrastructure—turning weeks of engineering into minutes of analysis.

*   **The Shadow Rule:** Growth infrastructure should be as automated as your CI/CD
    pipeline. If you're manually implementing analytics, onboarding flows, or viral
    mechanics, you're moving too slow.
*   **The Move:** Use Skene to identify growth opportunities, generate implementation
    code, and continuously measure impact. Every analysis improves the next. Your
    codebase becomes a growth engine, not just a product.

The leverage compounds: More codebases analyzed → Better pattern detection →
Faster growth implementation → More successful products.

───────────────────────────────────────────────────────────────────────────────

### 5. APPLY POWER DYNAMICS

*   **Control of Onboarding:** Build instant value delivery into your codebase. Auto-generate
    demo data, template workspaces, and guided flows. Users experience success before
    configuration, not after.
*   **Control of Retention:** Instrument every critical action. Measure time-to-value,
    activation rates, and feature adoption. Growth infrastructure surfaces what's working
    and what's not—automatically.
*   **Control of Virality:** Engineer sharing into your product. Export with attribution,
    public showcases, team invites. Every user action becomes a potential acquisition channel.

───────────────────────────────────────────────────────────────────────────────

### 6. THE "AVERAGE" TRAP

*   **The Common Path:** Building features without measuring impact. Shipping code and
    hoping it drives growth. Optimizing for "more" instead of "faster customer success."
*   **The Failure Point:** Feature-rich products with single-digit activation rates.
    Beautiful codebases with no growth infrastructure. Teams that build but never measure.

The average team ships features. The elite team engineers growth loops and measures
everything. Don't be average. Configure Skene and start measuring what actually matters.

───────────────────────────────────────────────────────────────────────────────

### 7. TECHNICAL EXECUTION

#### **Next Growth Loop: Automated Growth Infrastructure**

**Confidence:** 95%

**Exact Logic:**
1. Run `skene config` to set up your API key (2 minutes)
2. Run `skene analyze .` to get your growth infrastructure analysis
3. Review the growth-manifest.json for detected opportunities
4. Implement the highest-impact growth loops first
5. Re-run analysis to measure impact and iterate

**Exact Data Triggers:**
*   Codebase structure analysis (tech stack, frameworks, patterns)
*   Growth feature detection (analytics, onboarding, sharing mechanisms)
*   Opportunity identification (missing viral loops, friction points, activation gaps)

**Exact Stack/Steps:**
*   **Now:** Configure API key and run initial analysis
*   **Next:** Implement top 3 growth opportunities from the manifest
*   **Later:** Integrate Skene into CI/CD to continuously monitor growth infrastructure

**Get API keys:**
*   Gemini: https://aistudio.google.com/apikey
*   Anthropic: https://console.anthropic.com/
*   OpenAI: https://platform.openai.com/api-keys

───────────────────────────────────────────────────────────────────────────────

### 8. THE MEMO

**STATUS:** URGENT
**OBJECTIVE:** ENGINEER GROWTH INFRASTRUCTURE. MEASURE EVERYTHING. ITERATE FAST.

Growth is not about features. It's about helping customers succeed faster. Every
line of code should either deliver value or measure value delivery. If you're not
measuring, you're guessing. If you're guessing, you're losing.

This sample preview shows the format. The real analysis identifies YOUR specific
growth bottlenecks, YOUR missing infrastructure, YOUR optimization opportunities.

**Run this now:**

    skene config

Then analyze:

    skene analyze .

**Get API keys here:**
• Gemini: https://aistudio.google.com/apikey
• Anthropic: https://console.anthropic.com/
• OpenAI: https://platform.openai.com/api-keys

**End of Memo.**

"""
    return report


def show_sample_report(path: Path, output: Optional[Path] = None, exclude_folders: Optional[list[str]] = None):
    """
    Display sample growth analysis preview (no API key required).

    Shows the kind of strategic insights available with full API access.
    Automatically creates .skene.config file in the working directory if it doesn't exist.

    Args:
        path: Path to codebase
        output: Optional output path for JSON report (not used in sample mode)
        exclude_folders: Optional list of folders to exclude (not used in sample mode)
    """
    # Create config file in the working directory if it doesn't exist
    config_path = Path.cwd() / ".skene.config"
    if not config_path.exists():
        from skene.cli.config_manager import create_sample_config

        create_sample_config(config_path)
        console.print(
            f"[green]✓ Created config file:[/green] {config_path}\n"
            f"[dim]Edit this file to add your API key and customize settings.[/dim]\n"
        )

    console.print(
        Panel.fit(
            f"[bold blue]Growth Analysis Preview[/bold blue]\nPath: {path}\nMode: Sample Report (no API key required)",
            title="skene",
        )
    )

    # Generate and display sample report
    console.print()
    sample_report = generate_sample_growth_analysis()
    console.print(sample_report)

    # Call to action
    console.print()
    console.print(
        Panel.fit(
            "[bold yellow]Get and share this with team by configurating the api-key[/bold yellow]\n\n"
            "**Run this now:**\n\n"
            "    [bold cyan]skene config[/bold cyan]\n\n"
            "Then analyze:\n\n"
            "    [bold cyan]skene analyze .[/bold cyan]\n\n"
            "**Get API keys here:**\n"
            "• Gemini: https://aistudio.google.com/apikey\n"
            "• Anthropic: https://console.anthropic.com/\n"
            "• OpenAI: https://platform.openai.com/api-keys",
            title="🚀 Unlock Full Analysis",
            border_style="yellow",
        )
    )
