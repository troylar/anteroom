"""Tests for stable auth token derivation."""

from __future__ import annotations

from unittest.mock import MagicMock

from anteroom.app import _derive_auth_token


def _make_config(private_key: str | None = None) -> MagicMock:
    config = MagicMock()
    identity = MagicMock()
    if private_key:
        identity.private_key = private_key
        config.identity = identity
    else:
        config.identity = None
    return config


class TestDeriveAuthToken:
    def test_stable_same_key(self) -> None:
        """Same private key always produces the same token."""
        key = "-----BEGIN PRIVATE KEY-----\nfake-key-material\n-----END PRIVATE KEY-----"
        config = _make_config(private_key=key)
        token1 = _derive_auth_token(config)
        token2 = _derive_auth_token(config)
        assert token1 == token2
        assert len(token1) == 43

    def test_differs_per_key(self) -> None:
        """Different keys produce different tokens."""
        config_a = _make_config(private_key="key-alpha")
        config_b = _make_config(private_key="key-beta")
        assert _derive_auth_token(config_a) != _derive_auth_token(config_b)

    def test_fallback_no_identity(self) -> None:
        """Returns a random token when no identity is configured."""
        config = _make_config(private_key=None)
        token1 = _derive_auth_token(config)
        token2 = _derive_auth_token(config)
        # Random tokens should differ (extremely unlikely to collide)
        assert token1 != token2
        assert len(token1) > 20

    def test_fallback_empty_private_key(self) -> None:
        """Returns a random token when private key is empty string."""
        config = MagicMock()
        identity = MagicMock()
        identity.private_key = ""
        config.identity = identity
        token1 = _derive_auth_token(config)
        token2 = _derive_auth_token(config)
        assert token1 != token2

    def test_token_is_url_safe(self) -> None:
        """Derived token only contains URL-safe characters."""
        import re

        config = _make_config(private_key="test-key")
        token = _derive_auth_token(config)
        assert re.match(r"^[A-Za-z0-9_-]+$", token)
