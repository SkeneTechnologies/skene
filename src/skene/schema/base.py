"""Shared pydantic base for all wire models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class WireModel(BaseModel):
    """Base for everything serialized over the API.

    camelCase on the wire, snake_case in Python. ``extra="forbid"`` so
    typos in client payloads fail loudly instead of being dropped.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        serialize_by_alias=True,
    )
