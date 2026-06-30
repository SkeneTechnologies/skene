"""Secure storage for sensitive credentials via the OS keyring.

The LLM provider API key must not be written to disk in clear text (CWE-312).
Instead it is stored in the operating system keyring (macOS Keychain, Windows
Credential Manager, or a Secret Service backend on Linux).

All functions degrade gracefully: if no keyring backend is available (e.g. a
headless CI box) they return ``False``/``None`` instead of raising, so callers
can fall back to the ``SKENE_API_KEY`` environment variable.
"""

from __future__ import annotations

# Keyring service/account under which the provider API key is stored.
KEYRING_SERVICE = "skene"
API_KEY_ACCOUNT = "api_key"


def _keyring():
    """Return the keyring module, or None if it (or a backend) is unavailable."""
    try:
        import keyring
        from keyring.errors import NoKeyringError

        # Touch the backend so misconfigured environments fail here, not later.
        backend = keyring.get_keyring()
        if backend is None:
            return None
        return keyring
    except (ImportError, NoKeyringError, RuntimeError):
        return None


def set_api_key(api_key: str) -> bool:
    """Store the provider API key in the OS keyring.

    Returns True on success, False if no keyring backend is available.
    """
    kr = _keyring()
    if kr is None:
        return False
    try:
        kr.set_password(KEYRING_SERVICE, API_KEY_ACCOUNT, api_key)
        return True
    except Exception:
        return False


def get_api_key() -> str | None:
    """Retrieve the provider API key from the OS keyring, or None if unavailable."""
    kr = _keyring()
    if kr is None:
        return None
    try:
        value = kr.get_password(KEYRING_SERVICE, API_KEY_ACCOUNT)
    except Exception:
        return None
    return value or None


def delete_api_key() -> bool:
    """Remove the stored provider API key from the OS keyring.

    Returns True if a key was deleted, False otherwise (including when no
    backend is available or no key was stored).
    """
    kr = _keyring()
    if kr is None:
        return False
    try:
        from keyring.errors import PasswordDeleteError

        try:
            kr.delete_password(KEYRING_SERVICE, API_KEY_ACCOUNT)
            return True
        except PasswordDeleteError:
            return False
    except Exception:
        return False
