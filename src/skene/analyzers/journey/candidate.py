"""Intermediate milestone type produced by synthesis (or its classify fallback).

The subagents emit :class:`skene.schema.feature.Feature` (see
:mod:`skene.analyzers.journey.feature`); the synthesis step composes
groups of those features into candidate milestones — named from the
user's perspective, stage-assigned, evidence unioned. ``assemble`` then
buckets candidates into the final Journey. This type never crosses the
wire; it lives between two pipeline steps.
"""

from __future__ import annotations

from pydantic import Field

from skene.schema.feature import ID_PATTERN, Feature


class CandidateMilestone(Feature):
    """A synthesized milestone candidate, pre-assembly.

    Same evidence-bearing shape as a Feature, plus the stage assignment
    the synthesis step (or the per-feature classify fallback) decided.
    """

    stage_id: str = Field(pattern=ID_PATTERN)
