"""Intermediate milestone type emitted by the schema and code agents.

The model itself moved to :mod:`skene.schema.milestone` in phase 3 (it is
now the typed payload of ``MilestonePart`` on the wire); this module stays
as the engine-side import home.
"""

from __future__ import annotations

from skene.schema.milestone import CandidateMilestone as CandidateMilestone
