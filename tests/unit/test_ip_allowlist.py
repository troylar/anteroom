"""Tests for IP allowlist with CIDR support."""

from anteroom.services.ip_allowlist import check_ip_allowed


class TestCheckIpAllowed:
    """Tests for check_ip_allowed()."""

    def test_empty_allowlist_allows_all(self):
        assert check_ip_allowed("192.168.1.1", []) is True

    def test_exact_ipv4_match(self):
        assert check_ip_allowed("10.0.0.1", ["10.0.0.1"]) is True

    def test_exact_ipv4_no_match(self):
        assert check_ip_allowed("10.0.0.2", ["10.0.0.1"]) is False

    def test_cidr_ipv4_match(self):
        assert check_ip_allowed("10.0.0.50", ["10.0.0.0/24"]) is True

    def test_cidr_ipv4_no_match(self):
        assert check_ip_allowed("10.0.1.1", ["10.0.0.0/24"]) is False

    def test_cidr_wide_range(self):
        assert check_ip_allowed("10.255.255.255", ["10.0.0.0/8"]) is True

    def test_exact_ipv6_match(self):
        assert check_ip_allowed("::1", ["::1"]) is True

    def test_exact_ipv6_no_match(self):
        assert check_ip_allowed("::2", ["::1"]) is False

    def test_cidr_ipv6_match(self):
        assert check_ip_allowed("fe80::1", ["fe80::/10"]) is True

    def test_cidr_ipv6_no_match(self):
        assert check_ip_allowed("fe80::1", ["fd00::/8"]) is False

    def test_multiple_entries_match_second(self):
        assert check_ip_allowed("192.168.1.5", ["10.0.0.1", "192.168.1.0/24"]) is True

    def test_multiple_entries_no_match(self):
        assert check_ip_allowed("172.16.0.1", ["10.0.0.1", "192.168.1.0/24"]) is False

    def test_invalid_client_ip_denied(self):
        assert check_ip_allowed("not-an-ip", ["10.0.0.0/8"]) is False

    def test_invalid_allowlist_entry_skipped(self):
        assert check_ip_allowed("10.0.0.1", ["bad-entry", "10.0.0.1"]) is True

    def test_all_invalid_entries_denies(self):
        assert check_ip_allowed("10.0.0.1", ["bad1", "bad2"]) is False

    def test_localhost_ipv4(self):
        assert check_ip_allowed("127.0.0.1", ["127.0.0.0/8"]) is True

    def test_localhost_ipv6(self):
        assert check_ip_allowed("::1", ["::1/128"]) is True

    def test_mixed_ipv4_ipv6_entries(self):
        assert check_ip_allowed("192.168.1.1", ["::1", "192.168.1.0/24"]) is True
        assert check_ip_allowed("::1", ["192.168.1.0/24", "::1"]) is True

    def test_strict_false_for_cidr(self):
        """Non-strict mode allows host bits set in network address."""
        assert check_ip_allowed("192.168.1.100", ["192.168.1.1/24"]) is True
