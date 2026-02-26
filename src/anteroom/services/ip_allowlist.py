"""IP allowlist with CIDR support for network-level access control."""

from __future__ import annotations

import ipaddress
import logging
from typing import Sequence

logger = logging.getLogger(__name__)


def check_ip_allowed(client_ip: str, allowed_ips: Sequence[str]) -> bool:
    """Check if *client_ip* is permitted by *allowed_ips*.

    Returns ``True`` if the allowlist is empty (no restrictions) or if the
    client IP matches any entry.  Entries may be exact addresses
    (``192.168.1.5``) or CIDR ranges (``10.0.0.0/8``).  Both IPv4 and IPv6
    are supported.
    """
    if not allowed_ips:
        return True

    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        logger.warning("Invalid client IP address: %s — denying", client_ip)
        return False

    for entry in allowed_ips:
        try:
            if "/" in entry:
                network = ipaddress.ip_network(entry, strict=False)
                if addr in network:
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            logger.warning("Invalid allowlist entry: %s — skipping", entry)
            continue

    return False
