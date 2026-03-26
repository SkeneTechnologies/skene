"""
Command-line interface for skene.

Usage with uvx (recommended):
    uvx skene analyze .
    uvx skene plan
    uvx skene validate ./growth-manifest.json

Usage with pip install:
    skene analyze .
    skene plan
    skene validate ./growth-manifest.json
"""

from skene.cli.app import app

__all__ = ["app"]
