"""Egress domain allowlist for API call restrictions.

Validates that outbound API requests target only approved domains.
Pure functions — no I/O, no side effects.
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Sequence
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("anteroom.security")


def check_egress_allowed(
    url: str,
    allowed_domains: Sequence[str],
    block_localhost: bool = False,
) -> bool:
    """Check if *url*'s hostname is permitted for egress.

    Returns ``True`` if the allowlist is empty and ``block_localhost`` is
    ``False`` (no restrictions).  When *allowed_domains* is non-empty, the
    hostname must match an entry exactly (case-insensitive).

    Fails closed: unparseable URLs or empty hostnames are denied.
    """
    if not url or not url.strip():
        security_logger.warning("Empty egress URL — denying")
        return False

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        security_logger.warning("Invalid egress URL: %s — denying", url)
        return False

    if not host:
        security_logger.warning("No hostname in egress URL: %s — denying", url)
        return False

    if block_localhost and _is_loopback(host):
        security_logger.warning("Egress to localhost/loopback blocked: %s", host)
        return False

    if not allowed_domains:
        return True

    for entry in allowed_domains:
        if not entry or not isinstance(entry, str):
            logger.warning("Invalid allowlist entry: %r — skipping", entry)
            continue
        if host == entry.lower():
            return True

    security_logger.warning("Egress domain not in allowlist: %s", host)
    return False


def _is_loopback(host: str) -> bool:
    """Check if a hostname resolves to a loopback or localhost address."""
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_loopback
    except ValueError:
        return False
