"""FastAPI adapter over :mod:`skene.core`.

HTTP/SSE only — no engine logic lives here. ``create_app`` in
:mod:`skene.server.app` is the entry point.
"""

from skene.server.app import create_app

__all__ = ["create_app"]
