"""On-disk storage of journey artifacts and gold standards.

Journeys are written as JSON under ``journeys/<project_id>/<branch>/<commit>.json``.
Gold standards live at ``gold/<project_id>.json`` (minimal here; create/edit flows come
in a later slice).
"""

from __future__ import annotations

from pathlib import Path

from .config import Settings
from .journey import Journey


def _safe(component: str) -> str:
    """Make a branch name safe for use as a single path component."""
    return component.replace("/", "__")


class Storage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # --- journeys ------------------------------------------------------------
    def journey_path(self, project_id: str, branch: str, commit: str) -> Path:
        return self._settings.journeys_dir / project_id / _safe(branch) / f"{commit}.json"

    def save_journey(self, project_id: str, branch: str, commit: str, journey: Journey) -> Path:
        path = self.journey_path(project_id, branch, commit)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(journey.model_dump_json(by_alias=True, indent=2))
        return path

    def load_journey(self, path: Path) -> Journey:
        return Journey.model_validate_json(Path(path).read_text())

    # --- gold standard (seam for the gap-analysis slice) ---------------------
    def gold_path(self, project_id: str) -> Path:
        return self._settings.gold_dir / f"{project_id}.json"

    def save_gold(self, project_id: str, journey: Journey) -> Path:
        path = self.gold_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(journey.model_dump_json(by_alias=True, indent=2))
        return path

    def load_gold(self, project_id: str) -> Journey | None:
        path = self.gold_path(project_id)
        if not path.exists():
            return None
        return Journey.model_validate_json(path.read_text())
