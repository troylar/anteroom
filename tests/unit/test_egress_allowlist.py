"""Tests for egress domain allowlist."""

from __future__ import annotations

from anteroom.services.egress_allowlist import check_egress_allowed


class TestEmptyAllowlist:
    def test_empty_list_allows_all(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", []) is True

    def test_empty_list_allows_any_domain(self) -> None:
        assert check_egress_allowed("https://anything.example.com", []) is True

    def test_empty_list_allows_localhost(self) -> None:
        assert check_egress_allowed("http://localhost:11434/v1", []) is True


class TestExactDomainMatch:
    def test_exact_match(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", ["api.openai.com"]) is True

    def test_exact_match_no_path(self) -> None:
        assert check_egress_allowed("https://api.openai.com", ["api.openai.com"]) is True

    def test_no_match(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", ["api.anthropic.com"]) is False

    def test_subdomain_not_matched(self) -> None:
        assert check_egress_allowed("https://sub.api.openai.com", ["api.openai.com"]) is False

    def test_parent_not_matched(self) -> None:
        assert check_egress_allowed("https://openai.com", ["api.openai.com"]) is False

    def test_case_insensitive(self) -> None:
        assert check_egress_allowed("https://API.OPENAI.COM/v1", ["api.openai.com"]) is True

    def test_case_insensitive_allowlist(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", ["API.OPENAI.COM"]) is True

    def test_multiple_entries_match_first(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", ["api.openai.com", "api.anthropic.com"]) is True

    def test_multiple_entries_match_second(self) -> None:
        assert check_egress_allowed("https://api.anthropic.com/v1", ["api.openai.com", "api.anthropic.com"]) is True

    def test_multiple_entries_no_match(self) -> None:
        assert check_egress_allowed("https://api.mistral.ai/v1", ["api.openai.com", "api.anthropic.com"]) is False


class TestUrlParsing:
    def test_url_with_path(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1/chat/completions", ["api.openai.com"]) is True

    def test_url_with_port(self) -> None:
        assert check_egress_allowed("https://api.openai.com:443/v1", ["api.openai.com"]) is True

    def test_url_with_custom_port(self) -> None:
        assert check_egress_allowed("http://my-proxy.internal:8080/v1", ["my-proxy.internal"]) is True

    def test_url_with_query_params(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1?key=val", ["api.openai.com"]) is True

    def test_url_with_userinfo(self) -> None:
        assert check_egress_allowed("https://user:pass@api.openai.com/v1", ["api.openai.com"]) is True


class TestLocalhostBlocking:
    def test_localhost_allowed_by_default(self) -> None:
        assert check_egress_allowed("http://localhost:11434/v1", [], block_localhost=False) is True

    def test_localhost_blocked_when_enabled(self) -> None:
        assert check_egress_allowed("http://localhost:11434/v1", [], block_localhost=True) is False

    def test_127_0_0_1_blocked(self) -> None:
        assert check_egress_allowed("http://127.0.0.1:11434/v1", [], block_localhost=True) is False

    def test_ipv6_loopback_blocked(self) -> None:
        assert check_egress_allowed("http://[::1]:11434/v1", [], block_localhost=True) is False

    def test_localhost_localdomain_blocked(self) -> None:
        assert check_egress_allowed("http://localhost.localdomain:8080/v1", [], block_localhost=True) is False

    def test_external_domain_not_blocked(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", [], block_localhost=True) is True

    def test_localhost_in_allowlist_still_blocked(self) -> None:
        assert check_egress_allowed("http://localhost:11434/v1", ["localhost"], block_localhost=True) is False

    def test_127_in_allowlist_still_blocked(self) -> None:
        assert check_egress_allowed("http://127.0.0.1:11434/v1", ["127.0.0.1"], block_localhost=True) is False


class TestInvalidInput:
    def test_empty_url(self) -> None:
        assert check_egress_allowed("", ["api.openai.com"]) is False

    def test_whitespace_url(self) -> None:
        assert check_egress_allowed("   ", ["api.openai.com"]) is False

    def test_no_hostname(self) -> None:
        assert check_egress_allowed("file:///etc/passwd", ["api.openai.com"]) is False

    def test_invalid_allowlist_entry_skipped(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", ["", "api.openai.com"]) is True

    def test_none_allowlist_entry_skipped(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", [None, "api.openai.com"]) is True  # type: ignore[list-item]

    def test_all_invalid_entries_denies(self) -> None:
        assert check_egress_allowed("https://api.openai.com/v1", ["", None, ""]) is False  # type: ignore[list-item]

    def test_bare_hostname_url(self) -> None:
        # urlparse treats bare hostnames as path, not netloc — this is a known edge case
        # Users should always provide scheme://host format in base_url
        result = check_egress_allowed("api.openai.com", ["api.openai.com"])
        assert result is False  # no scheme = no hostname parsed


class TestLocalhostVariants:
    def test_127_0_0_1(self) -> None:
        assert check_egress_allowed("http://127.0.0.1:11434", ["127.0.0.1"]) is True

    def test_localhost_name(self) -> None:
        assert check_egress_allowed("http://localhost:11434", ["localhost"]) is True

    def test_ipv4_with_allowlist(self) -> None:
        assert check_egress_allowed("http://192.168.1.100:8080", ["192.168.1.100"]) is True

    def test_ipv4_not_in_allowlist(self) -> None:
        assert check_egress_allowed("http://192.168.1.100:8080", ["10.0.0.1"]) is False
