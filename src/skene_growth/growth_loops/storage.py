"""
Storage utilities for persisting growth loop definitions.

This module handles the generation and persistence of growth loop JSON files
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from rich.console import Console

from skene_growth.feature_registry import derive_feature_id
from skene_growth.llm.base import LLMClient

console = Console()


async def _show_progress_indicator(stop_event: asyncio.Event) -> None:
    """Show progress indicator with filled boxes every second."""
    count = 0
    while not stop_event.is_set():
        count += 1
        # Print filled box (█) every second
        console.print("[cyan]█[/cyan]", end="")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
            break
        except asyncio.TimeoutError:
            continue
    # Print newline when done
    if count > 0:
        console.print()


def derive_loop_name(technical_execution: dict[str, str]) -> str:
    """
    Extract the loop name from technical execution data.

    Takes the first non-empty line from the "next_build" field.

    Args:
        technical_execution: Dictionary containing "next_build" and other fields

    Returns:
        Loop name string, or "growth_loop" as fallback
    """
    next_build = technical_execution.get("next_build", "")
    if not next_build:
        return "growth_loop"

    # Get first non-empty line
    for line in next_build.split("\n"):
        line = line.strip()
        if line:
            return line

    return "growth_loop"


def derive_loop_id(loop_name: str) -> str:
    """
    Convert loop name to a valid snake_case identifier.

    Removes phase prefixes (e.g., "phase1_", "phase2_") from the result.

    Examples:
        "Phase 1: Share Flag" → "share_flag"
        "Phase 2: Discovery Engine" → "discovery_engine"
        "Discovery Engine" → "discovery_engine"

    Args:
        loop_name: Human-readable loop name

    Returns:
        Snake_case identifier matching pattern ^[a-z0-9_]+$ (without phase prefix)
    """
    # Convert to lowercase
    result = loop_name.lower()

    # Replace common separators and special chars with underscore
    result = re.sub(r"[:\-\s/\\]+", "_", result)

    # Remove any remaining non-alphanumeric chars (except underscore)
    result = re.sub(r"[^a-z0-9_]", "", result)

    # Collapse multiple underscores
    result = re.sub(r"_+", "_", result)

    # Strip leading/trailing underscores
    result = result.strip("_")

    # Remove phase prefixes (phase1_, phase2_, phase_1_, etc.)
    result = re.sub(r"^phase\d+_", "", result)
    result = re.sub(r"^phase_\d+_", "", result)

    # Strip leading/trailing underscores again after phase removal
    result = result.strip("_")

    # Ensure we have a valid identifier
    if not result or not re.match(r"^[a-z0-9_]+$", result):
        return "growth_loop"

    return result


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """
    Sanitize a string for use as a filename.

    - Replaces path separators and illegal characters with underscore
    - Collapses whitespace to single underscores
    - Trims to max_length
    - Ensures non-empty result

    Args:
        name: Raw filename string
        max_length: Maximum length (default 80 to leave room for timestamp)

    Returns:
        Sanitized filename safe for filesystem use
    """
    # Replace path separators and illegal filename chars
    result = re.sub(r'[/\\:*?"<>|]', "_", name)

    # Collapse whitespace to single underscores
    result = re.sub(r"\s+", "_", result)

    # Preserve trailing underscores before collapsing
    # Count trailing underscores (from consecutive illegal chars)
    trailing_underscore_count = 0
    if result.endswith("_"):
        trailing_underscore_count = len(result) - len(result.rstrip("_"))
        result = result.rstrip("_")

    # Collapse multiple underscores in the main part
    result = re.sub(r"_+", "_", result)

    # Strip leading underscores and whitespace
    result = result.lstrip("_ ")

    # If result is empty after processing, return fallback (don't restore trailing underscores)
    if not result:
        return "growth_loop"

    # Restore trailing underscores (preserve count from consecutive illegal chars)
    if trailing_underscore_count > 0:
        result = result + "_" * trailing_underscore_count

    # Enforce max length
    if len(result) > max_length:
        result = result[:max_length].rstrip("_")

    # Ensure non-empty (final check)
    if not result:
        return "growth_loop"

    return result


def generate_timestamped_filename(loop_id: str) -> str:
    """
    Generate a timestamped filename for the loop.

    Format: YYYYMMDD_HHMMSS_<loop_id>.json

    Args:
        loop_id: Snake_case loop identifier (already sanitized)

    Returns:
        Filename with timestamp prefix
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{loop_id}.json"


def format_features_for_prompt(features: list[dict[str, Any]]) -> str:
    """Format feature list for LLM prompt context."""
    if not features:
        return "(No known features — infer from technical execution and optionally define a new one.)"
    lines = [
        "Pick the best-matching feature for this loop, or define a new feature when none fits.",
        "Set linked_feature (human-readable name), linked_feature_id (snake_case), growth_pillars.",
        "",
        "Known features:",
    ]
    for f in features:
        fid = f.get("feature_id", "")
        name = f.get("feature_name", "?")
        pillars = f.get("growth_pillars", [])
        path = f.get("file_path", "")
        lines.append(f"- {name} (id: {fid}) — pillars: {pillars or 'none'} — {path}")
    return "\n".join(lines)


async def generate_loop_definition_with_llm(
    *,
    llm: LLMClient,
    technical_execution: dict[str, str],
    plan_path: Path,
    codebase_path: Path,
    run_target: Literal["skene_cloud", "supabase"] = "supabase",
    features: list[dict[str, Any]] | None = None,
    bias_feature_name: str | None = None,
) -> dict[str, Any]:
    """
    Generate a complete growth loop definition using LLM.

    The LLM analyzes the technical execution context and generates a loop definition
    that conforms to the GROWTH_LOOP_VERIFICATION_SPEC schema. The loop name and ID
    are automatically derived from the technical execution data.

    Args:
        llm: LLM client for generation
        technical_execution: Dictionary with next_build, confidence, exact_logic, etc.
        plan_path: Path to the growth plan file
        codebase_path: Path to the codebase root for analysis

    Returns:
        Complete loop definition dictionary conforming to schema with loop_id and name
    """
    # Derive loop name and ID from technical execution
    loop_name = derive_loop_name(technical_execution)
    loop_id = derive_loop_id(loop_name)

    # Build context from technical execution
    context_parts = []

    if technical_execution.get("next_build"):
        context_parts.append(f"**What We're Building:**\n{technical_execution['next_build']}")

    if technical_execution.get("confidence"):
        context_parts.append(f"**Confidence:** {technical_execution['confidence']}")

    if technical_execution.get("exact_logic"):
        context_parts.append(f"**Exact Logic:**\n{technical_execution['exact_logic']}")

    if technical_execution.get("data_triggers"):
        context_parts.append(f"**Data Triggers:**\n{technical_execution['data_triggers']}")

    if technical_execution.get("sequence"):
        context_parts.append(f"**Sequence:**\n{technical_execution['sequence']}")

    context = "\n\n".join(context_parts)

    # Load database schema for table-aware telemetry
    schema_path = plan_path.parent / "schema.md"
    schema_context = ""
    if schema_path.exists():
        schema_context = schema_path.read_text(encoding="utf-8")

    # Telemetry instructions based on run target
    if run_target == "skene_cloud":
        _telemetry_backend = "Skene Cloud / action.skene.ai"
        _telemetry_instructions = """
- **CRITICAL: Include ONLY ONE telemetry event - the single most meaningful action for this loop**
- Define a code location where the app MUST call the action.skene.ai API
- The single telemetry item must have:
  - `type` (string, required): "skene_cloud"
  - `action_name` (string, required): Unique identifier (snake_case, e.g., "document_created")
  - `endpoint` (string, required): "https://action.skene.ai" (or equivalent API base)
  - `description` (string, required): What this action represents for growth measurement
  - `properties` (array of strings, required): Payload keys to send (e.g., ["workspace_id", "id", "created_at"])
  - `location` (object, required): Where in code to add the call:
    - `file` (string): Path to the file (e.g., "src/api/documents.py")
    - `context` (string): Where in the file (e.g., "after document save", "in create_document handler")
- Implementation: HTTP POST to action.skene.ai with JSON payload {{action_name, ...properties}}
- Example: `{{"type": "skene_cloud", "action_name": "document_created", "endpoint": "https://action.skene.ai",
    "description": "Tracks when a new document is persisted — activation milestone",
    "properties": ["workspace_id", "id", "created_at"],
    "location": {{"file": "src/api/documents.py", "context": "after document save"}}}}`
"""
    else:
        _telemetry_backend = "Supabase / database triggers"
        _telemetry_instructions = """
- **CRITICAL: Include ONLY ONE telemetry event - the single most meaningful action for this loop**
- Pick the ONE data state change that best signals this loop is working
- Focus on DATA STATE CHANGES in the database, NOT app-side event emission
- Define telemetry as database triggers that fire on INSERT, UPDATE, or DELETE
- Use the Database Schema above to identify which tables and columns matter
- The single telemetry item must have:
  - `type` (string, required): "supabase"
  - `action_name` (string, required): Unique identifier (snake_case, e.g., "document_created")
  - `table` (string, required): Database table where the change occurs
  - `operation` (string, required): One of "INSERT", "UPDATE", "DELETE"
  - `description` (string, required): What this data change represents for growth measurement
  - `properties` (array of strings, required): Column names for the trigger payload
- Implementation: PostgreSQL AFTER INSERT/UPDATE/DELETE trigger that writes to telemetry
- Example: `{{"type": "supabase", "action_name": "document_created", "table": "documents", "operation": "INSERT",
    "description": "Tracks when a new document is persisted — activation milestone",
    "properties": ["workspace_id", "id", "created_at"]}}`
"""
    _telemetry_instructions += "\n- **Remember: Only ONE telemetry item. Choose the most important one.**"

    features_context = format_features_for_prompt(features) if features else format_features_for_prompt([])
    bias_note = ""
    if bias_feature_name:
        bias_note = f"\n**Strongly prefer linking to feature: {bias_feature_name}**"

    # Construct the LLM prompt
    prompt = (
        f"""You are a growth engineering expert. Generate a complete growth loop definition """
        f"""that conforms to the GROWTH_LOOP_VERIFICATION_SPEC schema.

## Schema Requirements

The output MUST be a valid JSON object with these REQUIRED fields:

- `loop_id` (string): Snake_case identifier matching pattern ^[a-z0-9_]+$ (e.g., "phase1_share_flag")
- `name` (string): Human-readable name of the growth loop
- `description` (string): Detailed description of what this loop accomplishes
- `linked_feature` (string): Human-readable feature name this loop implements or enhances
- `linked_feature_id` (string): Snake_case ID for programmatic linking (must match a known feature_id, or derive from linked_feature)
- `growth_pillars` (array of strings): 0–3 of "onboarding", "engagement", "retention"
- `requirements` (object):
  - `files` (array): File requirements with path, purpose, required, checks
    (checks: array of objects with type, pattern, description)
  - `functions` (array): Function requirements with file, name, required,
    signature, logic (logic field is REQUIRED)
  - `integrations` (array): Integration requirements with type, description,
    verification
  - `telemetry` (array): See TELEMETRY section below. **MUST contain exactly ONE item**.
- `dependencies` (array of strings): Loop IDs this depends on (use empty array [] if none)
- `verification_commands` (array of strings): Manual verification commands
- `test_coverage` (object):
  - `unit_tests` (array of strings)
  - `integration_tests` (array of strings)
  - `manual_tests` (array of strings)
- `metrics` (object):
  - `data_actions` (array of strings): Must contain the single action_name from the one telemetry item
  - `success_criteria` (array of strings)

## Technical Execution Context

{context}

## Codebase Information

- Codebase path: {codebase_path}
- Growth plan: {plan_path}

## Feature Linking
{features_context}
{bias_note}

## Database Schema

{schema_context if schema_context else "(No schema.md found — infer tables from the project context.)"}

## Your Task

Analyze the technical execution context and generate a complete, actionable growth loop definition.

**For `requirements.files`:**
- Identify specific files that need to be created or modified
- Provide a `purpose` description for each file explaining its role
- Define `checks` as an array of objects (NOT strings) with this structure:
  - `type` (string, required): One of "contains", "function_exists", "class_exists", "import_exists"
  - `pattern` (string, required): The pattern, function name, class name, or import to check for
  - `description` (string, required): A clear, human-readable explanation of what this check verifies
  Example: `{{"type": "function_exists", "pattern": "scan_for_leaks",
    "description": "Function 'scan_for_leaks' must exist in this file"}}`
  Example: `{{"type": "contains", "pattern": "stripe.Charge.create",
    "description": "File must contain code that calls stripe.Charge.create"}}`

**For `requirements.functions`:**
- List key functions that need to exist
- Specify which file each function should be in
- Include a `signature` field with the function signature (e.g., "function_name(arg1: type) -> return_type")
- **CRITICAL**: Always include a `logic` field that clearly describes what the function should do, including:
  - What inputs it processes and their purpose
  - What operations or transformations it performs
  - What it returns and the structure of the return value
  - Any important side effects, error handling, or edge cases
  The logic description should be detailed enough that a developer can
  implement the function without ambiguity.
  Example: `{{"name": "detect_revenue_leaks", "logic": "Scans the given
    directory path recursively for revenue leak patterns using hardcoded regex
    patterns. Returns a list of dictionaries, each containing leak details
    with keys: 'type' (str), 'location' (str), 'severity' (str),
    'pattern_matched' (str)."}}`

**For `requirements.integrations`:**
- Identify integration points (cli_flag, api_endpoint, ui_component, external_service)
- Provide verification commands

**For `requirements.telemetry` ({_telemetry_backend}):**
{_telemetry_instructions}

**For `verification_commands`:**
- Provide concrete commands that can verify the implementation

**For `test_coverage`:**
- Suggest unit tests, integration tests, and manual test steps

**For `metrics`:**
- List data actions to track (action_name values from telemetry)
- Define success criteria (KPIs)

Return ONLY the JSON object, no markdown code fences, no explanations. The JSON must be valid and parseable."""
    )

    # Start progress indicator for generation
    stop_event = asyncio.Event()
    progress_task = None

    try:
        progress_task = asyncio.create_task(_show_progress_indicator(stop_event))
        response = await llm.generate_content(prompt)

        # Clean up response - remove markdown code fences if present
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            # Find start and end of JSON
            start_idx = 0
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start_idx == 0:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            response = "\n".join(lines[start_idx:end_idx])

        # Parse JSON
        loop_def = json.loads(response)

        # Ensure required fields are present (use derived values as fallback)
        if "loop_id" not in loop_def or not loop_def["loop_id"]:
            loop_def["loop_id"] = loop_id
        if "name" not in loop_def or not loop_def["name"]:
            loop_def["name"] = loop_name

        # Validate loop_id format (must match ^[a-z0-9_]+$)
        if not re.match(r"^[a-z0-9_]+$", loop_def["loop_id"]):
            # If LLM generated invalid format, use our derived one
            loop_def["loop_id"] = loop_id

        # Ensure requirements structure exists
        if "requirements" not in loop_def:
            loop_def["requirements"] = {}
        if "files" not in loop_def["requirements"]:
            loop_def["requirements"]["files"] = []
        if "functions" not in loop_def["requirements"]:
            loop_def["requirements"]["functions"] = []
        if "integrations" not in loop_def["requirements"]:
            loop_def["requirements"]["integrations"] = []
        if "telemetry" not in loop_def["requirements"]:
            loop_def["requirements"]["telemetry"] = []

        # Ensure each telemetry item has correct type
        for item in loop_def["requirements"]["telemetry"]:
            if isinstance(item, dict) and "type" not in item:
                item["type"] = run_target

        # Ensure other required fields with defaults
        if "dependencies" not in loop_def:
            loop_def["dependencies"] = []
        if "verification_commands" not in loop_def:
            loop_def["verification_commands"] = []
        if "test_coverage" not in loop_def:
            loop_def["test_coverage"] = {
                "unit_tests": [],
                "integration_tests": [],
                "manual_tests": [],
            }
        if "metrics" not in loop_def:
            loop_def["metrics"] = {
                "data_actions": [],
                "success_criteria": [],
            }

        # Ensure feature linking fields (derive from name/plan if missing)
        if not loop_def.get("linked_feature"):
            loop_def["linked_feature"] = loop_def.get("name", loop_name)
        if not loop_def.get("linked_feature_id"):
            loop_def["linked_feature_id"] = derive_feature_id(loop_def["linked_feature"])
        if "growth_pillars" not in loop_def:
            loop_def["growth_pillars"] = []

        return loop_def

    except json.JSONDecodeError:
        # Fallback: Create minimal valid loop definition
        return {
            "loop_id": loop_id,
            "name": loop_name,
            "description": technical_execution.get("next_build", "Growth loop implementation")[:500],
            "linked_feature": loop_name,
            "linked_feature_id": derive_feature_id(loop_name),
            "growth_pillars": [],
            "requirements": {
                "files": [],
                "functions": [],
                "integrations": [],
                "telemetry": [],
            },
            "dependencies": [],
            "verification_commands": [],
            "test_coverage": {
                "unit_tests": [],
                "integration_tests": [],
                "manual_tests": [],
            },
            "metrics": {
                "data_actions": [],
                "success_criteria": [],
            },
        }
    finally:
        # Stop progress indicator
        if progress_task is not None:
            stop_event.set()
            try:
                await progress_task
            except Exception:
                pass


def write_growth_loop_json(
    *,
    base_dir: Path,
    filename: str,
    payload: dict[str, Any],
) -> Path:
    """
    Write growth loop definition to JSON file.

    Creates the growth-loops directory if needed and writes the payload
    as pretty-printed JSON.

    Args:
        base_dir: Base output directory (e.g., ./skene-context)
        filename: Filename including .json extension
        payload: Complete loop definition dictionary

    Returns:
        Path to the written file
    """
    # Create growth-loops directory
    loops_dir = base_dir / "growth-loops"
    loops_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON file
    output_path = loops_dir / filename
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return output_path


def load_existing_growth_loops(base_dir: Path) -> list[dict[str, Any]]:
    """
    Load all existing growth loop definitions from growth-loops directory.

    Args:
        base_dir: Base directory (e.g., ./skene-context)

    Returns:
        List of growth loop definition dictionaries, sorted by timestamp (newest first)
    """
    from loguru import logger

    loops_dir = base_dir / "growth-loops"

    # Return empty list if directory doesn't exist
    if not loops_dir.exists() or not loops_dir.is_dir():
        return []

    growth_loops = []

    # Read all JSON files
    for json_file in loops_dir.glob("*.json"):
        try:
            content = json_file.read_text(encoding="utf-8")
            loop_data = json.loads(content)

            # Extract timestamp from filename for sorting
            # Expected format: YYYYMMDD_HHMMSS_<loop_id>.json
            filename = json_file.stem  # Without .json extension
            timestamp_match = re.match(r"^(\d{8}_\d{6})_", filename)
            if timestamp_match:
                timestamp_str = timestamp_match.group(1)
                try:
                    loop_data["_file_timestamp"] = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except ValueError:
                    # If parsing fails, use file modification time
                    loop_data["_file_timestamp"] = datetime.fromtimestamp(json_file.stat().st_mtime)
            else:
                # Use file modification time if no timestamp in filename
                loop_data["_file_timestamp"] = datetime.fromtimestamp(json_file.stat().st_mtime)

            loop_data["_source_file"] = str(json_file)
            growth_loops.append(loop_data)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse growth loop JSON {json_file}: {e}")
            continue
        except Exception as e:
            logger.warning(f"Failed to read growth loop file {json_file}: {e}")
            continue

    # Sort by timestamp (newest first)
    growth_loops.sort(key=lambda x: x.get("_file_timestamp", datetime.min), reverse=True)

    return growth_loops


def format_growth_loops_summary(loops: list[dict[str, Any]]) -> str:
    """
    Format growth loops into a summary string for inclusion in prompts.

    Args:
        loops: List of growth loop dictionaries

    Returns:
        Formatted string describing existing growth loops
    """
    if not loops:
        return ""

    lines = [
        "## Existing Growth Loops",
        "",
        f"The following {len(loops)} growth loop(s) have already been defined for this project.",
        "**DO NOT suggest duplicate features or opportunities that overlap with these existing loops.**",
        "Instead, focus on complementary opportunities or suggest enhancements to existing loops.",
        "",
    ]

    for i, loop in enumerate(loops, 1):
        loop_id = loop.get("loop_id", "unknown")
        loop_name = loop.get("name", "Unnamed Loop")
        description = loop.get("description", "No description available")

        lines.append(f"### {i}. {loop_name} (ID: `{loop_id}`)")
        lines.append(f"**Description:** {description}")

        # Include requirements summary
        requirements = loop.get("requirements", {})

        files = requirements.get("files", [])
        if files:
            file_count = len(files)
            lines.append(f"**Files:** {file_count} file(s) to create/modify")
            # Show first 2 file paths as examples
            for file_req in files[:2]:
                file_path = file_req.get("path", "unknown")
                lines.append(f"  - `{file_path}`")
            if file_count > 2:
                lines.append(f"  - ... and {file_count - 2} more")

        functions = requirements.get("functions", [])
        if functions:
            func_count = len(functions)
            lines.append(f"**Functions:** {func_count} function(s) to implement")

        integrations = requirements.get("integrations", [])
        if integrations:
            int_types = [i.get("type", "unknown") for i in integrations]
            lines.append(f"**Integrations:** {', '.join(int_types)}")

        telemetry = requirements.get("telemetry", [])
        if telemetry:
            labels = []
            for t in telemetry[:3]:
                name = t.get("action_name", "unknown")
                table = t.get("table", "")
                op = t.get("operation", "")
                loc = t.get("location", {})
                if table:
                    suffix = f" ({table} {op})"
                elif loc:
                    file = loc.get("file", "?")
                    suffix = f" ({file})"
                else:
                    suffix = ""
                labels.append(f"{name}{suffix}")
            lines.append(f"**Data Actions:** {', '.join(labels)}")

        # Include dependencies
        dependencies = loop.get("dependencies", [])
        if dependencies:
            lines.append(f"**Dependencies:** {', '.join(dependencies)}")

        lines.append("")  # Blank line between loops

    return "\n".join(lines)
