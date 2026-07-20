"""Tests for assemble_journey (Step 5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from skene.analyzers.journey.assemble import assemble_journey
from skene.analyzers.journey.candidate import CandidateMilestone
from skene.analyzers.journey.models import Evidence


def _candidate(
    pid: str,
    name: str,
    stage_id: str,
    *,
    confidence: float = 0.8,
    source: str = "code",
) -> CandidateMilestone:
    evidence = (
        Evidence(source="code", path=f"src/{pid}.ts", reason="found")
        if source == "code"
        else Evidence(source="db", table=pid, reason="row")
    )
    return CandidateMilestone(
        proposed_id=pid,
        name=name,
        description=name,
        evidence=[evidence],
        confidence=confidence,
        stage_id=stage_id,
    )


def test_groups_by_stage_and_assigns_sequential_order():
    candidates = [
        _candidate("landing", "Landing", "discovery"),
        _candidate("signup", "Sign Up", "discovery"),
        _candidate("api_key", "API Key", "onboarding"),
    ]
    journey = assemble_journey(candidates, product_name="Test")
    stage_ids = [s.id for s in journey.stages]
    assert stage_ids == ["discovery", "onboarding"]

    discovery = journey.stages[0]
    assert len(discovery.milestones) == 2
    assert [m.order for m in discovery.milestones] == [1, 2]
    # Sorted alphabetically by proposed_id → landing < signup
    assert [m.id for m in discovery.milestones] == ["landing", "signup"]


def test_id_collision_within_stage_gets_suffixed():
    candidates = [
        _candidate("signup", "Signup A", "discovery"),
        _candidate("signup", "Signup B", "discovery"),
    ]
    journey = assemble_journey(candidates, product_name="Test")
    ids = [m.id for m in journey.stages[0].milestones]
    assert ids == ["signup", "signup_2"]


def test_empty_candidate_list_raises():
    with pytest.raises(ValueError, match="no synthesized milestones"):
        assemble_journey([], product_name="Test")


def test_layers_only_include_present_stages():
    candidates = [
        _candidate("landing", "Landing", "discovery"),
        _candidate("api_key", "API Key", "onboarding"),
    ]
    journey = assemble_journey(candidates, product_name="Test")
    layer_ids = [layer.id for layer in journey.layers]
    # Only L1 (discovery) and L2 (onboarding+activation) are present
    assert "L1" in layer_ids
    assert "L2" in layer_ids
    assert "L3" not in layer_ids
    assert "L4" not in layer_ids
    # L2 must only list onboarding (activation is absent)
    l2 = next(layer for layer in journey.layers if layer.id == "L2")
    assert l2.spans_stages == ["onboarding"]


def test_round_trip_validates_via_pydantic():
    candidates = [_candidate("landing", "Landing", "discovery")]
    journey = assemble_journey(
        candidates,
        product_name="Test",
        generated_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
    )
    # The assemble step always round-trips through model_validate, so we
    # just check the result has the expected shape.
    assert journey.product.name == "Test"
    assert journey.stages[0].milestones[0].name == "Landing"
