"""Tests for the Journey Pydantic schema."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from skene.analyzers.journey.models import Journey
from skene.analyzers.journey.serialize import to_json, to_yaml, write

VALID_DOC: dict = {
    "product": {
        "name": "Ballpark",
        "description": "AI estimate widget for agencies",
        "generated_at": "2026-05-11T10:00:00Z",
        "source_commit": "abc123",
    },
    "layers": [
        {"id": "L1", "name": "Onboarding", "spans_stages": ["discovery", "onboarding"]},
    ],
    "stages": [
        {
            "id": "discovery",
            "order": 1,
            "name": "Discovery",
            "subtitle": "The Hook",
            "milestones": [
                {
                    "id": "landing_view",
                    "order": 1,
                    "name": "Landing Page View",
                    "description": "Visitor lands on marketing site.",
                    "evidence": [
                        {
                            "source": "code",
                            "path": "src/pages/index.tsx",
                            "reason": "Marketing landing route",
                        }
                    ],
                }
            ],
        },
        {
            "id": "onboarding",
            "order": 2,
            "name": "Onboarding",
            "milestones": [
                {
                    "id": "api_key_configured",
                    "order": 1,
                    "name": "API Key Configured",
                    "description": "User enters their API key.",
                    "evidence": [
                        {
                            "source": "db",
                            "table": "user_settings",
                            "reason": "Stores the user's API key",
                        }
                    ],
                }
            ],
        },
    ],
    "connectors": [
        {
            "id": "signup_to_setup",
            "from": "discovery.landing_view",
            "to": "onboarding.api_key_configured",
            "label": "Welcome Email",
            "trigger_type": "email",
            "evidence": [
                {
                    "source": "code",
                    "path": "src/jobs/sendWelcome.ts",
                    "reason": "Welcome email sent after signup",
                }
            ],
        }
    ],
}


def fresh_doc() -> dict:
    return copy.deepcopy(VALID_DOC)


def test_full_valid_doc_parses():
    Journey.model_validate(VALID_DOC)


def test_yaml_roundtrip(tmp_path: Path):
    journey = Journey.model_validate(VALID_DOC)
    out = tmp_path / "journey.yaml"
    write(journey, out)
    text = out.read_text()
    # 'from' alias used, not 'from_'
    assert "from: discovery.landing_view" in text
    assert "from_:" not in text


def test_json_roundtrip(tmp_path: Path):
    journey = Journey.model_validate(VALID_DOC)
    out = tmp_path / "journey.json"
    write(journey, out)
    text = out.read_text()
    assert '"from": "discovery.landing_view"' in text


def test_to_yaml_and_to_json_return_strings():
    journey = Journey.model_validate(VALID_DOC)
    assert isinstance(to_yaml(journey), str)
    assert isinstance(to_json(journey), str)


def test_code_evidence_without_path_fails():
    doc = fresh_doc()
    doc["stages"][0]["milestones"][0]["evidence"] = [{"source": "code", "reason": "missing path"}]
    with pytest.raises(ValidationError, match="requires 'path'"):
        Journey.model_validate(doc)


def test_db_evidence_without_table_fails():
    doc = fresh_doc()
    doc["stages"][0]["milestones"][0]["evidence"] = [{"source": "db", "reason": "missing table"}]
    with pytest.raises(ValidationError, match="requires 'table'"):
        Journey.model_validate(doc)


def test_duplicate_stage_ids_fail():
    doc = fresh_doc()
    doc["stages"].append(copy.deepcopy(doc["stages"][0]))
    doc["stages"][-1]["order"] = 99
    with pytest.raises(ValidationError, match="stage ids must be unique"):
        Journey.model_validate(doc)


def test_duplicate_milestone_ids_within_stage_fail():
    doc = fresh_doc()
    dup = copy.deepcopy(doc["stages"][0]["milestones"][0])
    dup["order"] = 2
    doc["stages"][0]["milestones"].append(dup)
    with pytest.raises(ValidationError, match="milestone ids must be unique"):
        Journey.model_validate(doc)


def test_same_milestone_id_in_different_stages_is_ok():
    doc = fresh_doc()
    doc["stages"][0]["milestones"][0]["id"] = "shared"
    doc["stages"][1]["milestones"][0]["id"] = "shared"
    doc["connectors"][0]["from"] = "discovery.shared"
    doc["connectors"][0]["to"] = "onboarding.shared"
    Journey.model_validate(doc)


def test_layer_referencing_unknown_stage_fails():
    doc = fresh_doc()
    doc["layers"][0]["spans_stages"] = ["discovery", "ghost_stage"]
    with pytest.raises(ValidationError, match="unknown stages"):
        Journey.model_validate(doc)


def test_connector_to_unknown_literal_is_allowed():
    doc = fresh_doc()
    doc["connectors"][0]["to"] = "unknown"
    doc["connectors"][0]["confidence"] = 0.3
    Journey.model_validate(doc)


def test_write_rejects_unknown_extension(tmp_path: Path):
    journey = Journey.model_validate(VALID_DOC)
    with pytest.raises(ValueError, match="unsupported file type"):
        write(journey, tmp_path / "out.txt")
