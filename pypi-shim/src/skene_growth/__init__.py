"""Transitional package: skene-growth has been renamed to skene.

Install the new package:
    pip install skene

All functionality is now available under the 'skene' package name.
"""

import warnings

warnings.warn(
    "The 'skene-growth' package has been renamed to 'skene'. Please update your dependencies: pip install skene",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from skene for backward compatibility
from skene import *  # noqa: E402, F401, F403
