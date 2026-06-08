"""Entrypoint: ``python -m skened`` runs the API server (used by ``skene up``)."""

from __future__ import annotations

import logging

import uvicorn

from .config import get_settings


def main() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run("skened.api:app", host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
