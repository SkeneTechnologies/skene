"""
Command-line interface for skene.

Usage with uvx (recommended):
    uvx skene analyse-journey .

Usage with pip install:
    skene analyse-journey .
"""

from skene.cli.app import app

__all__ = ["app"]
