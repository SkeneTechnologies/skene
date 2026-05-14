"""Agentic journey-map generation pipeline.

Replaces the legacy ``schema_journey`` / ``growth_from_schema`` /
``journey_compiler`` flow for ``analyse-journey``. Two parallel agents
(schema + code) emit candidate milestones, which are merged, classified
into seven canonical stages, and assembled into a validated
:class:`skene.analyzers.journey.models.Journey`.
"""
