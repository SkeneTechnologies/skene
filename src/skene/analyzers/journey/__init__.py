"""Agentic journey-map generation: models, prompts, and pipeline steps.

Two subagents (schema + code) emit candidate milestones, which are
merged, classified into seven canonical stages, and assembled into a
validated :class:`skene.analyzers.journey.models.Journey`. Orchestration
lives in :mod:`skene.core.journey` (the main skene agent + task tool);
this package holds the engine pieces it drives.
"""
