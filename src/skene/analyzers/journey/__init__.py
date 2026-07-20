"""Agentic journey-map generation: models, prompts, and pipeline steps.

Two subagents (schema + code) emit product features, which are merged
into the deduplicated feature map, synthesized into stage-assigned
milestones, and assembled into a validated
:class:`skene.analyzers.journey.models.Journey`. Orchestration
lives in :mod:`skene.core.journey` (the main skene agent + task tool);
this package holds the engine pieces it drives.
"""
