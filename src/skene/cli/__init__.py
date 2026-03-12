"""
Command-line interface for skene.

Usage with uvx (recommended):
    uvx skene analyze .
    uvx skene plan
    uvx skene chat .
    uvx skene validate ./growth-manifest.json

Usage with pip install:
    skene analyze .
    skene plan
    skene chat .
    skene validate ./growth-manifest.json
"""

from skene.cli.main import app

__all__ = ["app"]
