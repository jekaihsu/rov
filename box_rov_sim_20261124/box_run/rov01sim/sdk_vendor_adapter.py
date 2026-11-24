"""Internal SDK wire-protocol compatibility normalizer.

Maps legacy 2-letter prefixed SDK class names onto ROV-01 neutral class names
at the RPC boundary when not running in --release-mode.
"""
from __future__ import annotations

import os
import re

_VENDOR_PREFIX = re.compile(r"^[A-Za-z]{2}(?=(?:Rov|Camera|SDK))")


def normalize_class(cls: str) -> str:
    """Strip legacy 2-letter prefix from SDK class names unless release_mode is active."""
    if os.environ.get("ROV01SIM_RELEASE_MODE") == "1":
        return str(cls)
    return _VENDOR_PREFIX.sub("", str(cls))
