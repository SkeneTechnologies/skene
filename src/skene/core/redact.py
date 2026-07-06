"""Secret redaction for anything that gets persisted or streamed.

``db_url`` is deliberately never stored (see the design doc's watch-outs):
sessions record only the display form produced here.
"""

from __future__ import annotations

import re

# scheme://user:password@  →  scheme://user:***@
_DSN_CREDENTIALS = re.compile(r"(\w[\w+.-]*://[^:/?#@\s]+):[^@\s]+@")


def redact_dsn_in_text(text: str) -> str:
    """Redact the password of any ``scheme://user:pass@`` URL inside ``text``.

    Safe on arbitrary prose: URLs without credentials pass through untouched.
    """
    return _DSN_CREDENTIALS.sub(r"\1:***@", text)


def redact_db_url(url: str) -> str:
    """Return a display-safe version of a DB URL with the password redacted.

    Examples::

        postgresql://user:secret@host:5432/mydb  →  postgresql://user:***@host:5432/mydb
        postgresql://user@host/mydb              →  postgresql://user@host/mydb
    """
    try:
        if "://" not in url:
            return "<redacted>"

        scheme, rest = url.split("://", 1)

        if "@" in rest:
            creds, remainder = rest.split("@", 1)
            if ":" in creds and not creds.endswith(":"):
                user = creds.split(":", 1)[0]
                rest = f"{user}:***@{remainder}"
            else:
                rest = f"{creds}@{remainder}"

        return f"{scheme}://{rest}"
    except Exception:  # noqa: BLE001 — never let redaction leak by failing
        return "<redacted>"
