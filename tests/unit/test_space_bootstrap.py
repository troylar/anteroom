"""Unit tests for services/space_bootstrap.py — Space bootstrap."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from anteroom.services.space_bootstrap import (
    BootstrapResult,
    CloneResult,
    _extract_repo_name,
    bootstrap_space,
    clone_repos,
)
from anteroom.services.spaces import SpaceConfig


class TestExtractRepoName:
    def test_https_url(self) -> None:
        assert _extract_repo_name("https://github.com/org/repo.git") == "repo"

    def test_trailing_slash(self) -> None:
        assert _extract_repo_name("https://github.com/org/repo/") == "repo"

    def test_no_git_suffix(self) -> None:
        assert _extract_repo_name("https://github.com/org/repo") == "repo"


class TestCloneRepos:
    def test_skips_existing(self, tmp_path: Path) -> None:
        (tmp_path / "repo").mkdir()
        results = clone_repos(["https://github.com/org/repo.git"], tmp_path)
        assert len(results) == 1
        assert results[0].success is True

    def test_bad_url_scheme(self, tmp_path: Path) -> None:
        results = clone_repos(["ext::ssh://evil"], tmp_path)
        assert len(results) == 1
        assert results[0].success is False
        assert "URL scheme not allowed" in results[0].error

    @patch("anteroom.services.space_bootstrap.subprocess.run")
    def test_clone_success(self, mock_run: object, tmp_path: Path) -> None:
        results = clone_repos(["https://github.com/org/newrepo.git"], tmp_path)
        assert len(results) == 1
        assert results[0].success is True


class TestBootstrapSpace:
    @patch("anteroom.services.space_bootstrap.clone_repos")
    def test_bootstrap_with_repos(self, mock_clone: object, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        mock_clone.return_value = [CloneResult(url="https://github.com/org/repo.git", success=True)]
        cfg = SpaceConfig(name="test", repos=["https://github.com/org/repo.git"])
        result = bootstrap_space(MagicMock(), cfg, None, tmp_path)
        assert isinstance(result, BootstrapResult)
        assert len(result.clone_results) == 1
        assert result.errors == []

    @patch("anteroom.services.space_bootstrap.clone_repos")
    def test_bootstrap_records_errors(self, mock_clone: object, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        mock_clone.return_value = [CloneResult(url="https://bad.git", success=False, error="fail")]
        cfg = SpaceConfig(name="test", repos=["https://bad.git"])
        result = bootstrap_space(MagicMock(), cfg, None, tmp_path)
        assert len(result.errors) == 1

    @patch("anteroom.services.space_bootstrap.clone_repos")
    def test_bootstrap_with_local_repos_root(self, mock_clone: object, tmp_path: Path) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        custom_root = tmp_path / "custom"
        custom_root.mkdir()
        mock_clone.return_value = []
        local_cfg = SimpleNamespace(repos_root=str(custom_root))
        cfg = SpaceConfig(name="test", repos=["https://github.com/org/repo.git"])
        bootstrap_space(MagicMock(), cfg, local_cfg, tmp_path)
        mock_clone.assert_called_once_with(["https://github.com/org/repo.git"], custom_root)

    @patch("anteroom.services.space_bootstrap.clone_repos")
    def test_bootstrap_with_packs(self, mock_clone: object, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        mock_clone.return_value = []
        cfg = SpaceConfig(name="test", repos=[], packs=["ns/pack1", "ns/pack2"], pack_sources=[])
        result = bootstrap_space(MagicMock(), cfg, None, tmp_path)
        assert result.installed_packs == ["ns/pack1", "ns/pack2"]


class TestCloneReposErrors:
    @patch("anteroom.services.space_bootstrap.subprocess.run")
    def test_clone_called_process_error(self, mock_run: object, tmp_path: Path) -> None:
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="fatal: repo not found")
        results = clone_repos(["https://github.com/org/missing.git"], tmp_path)
        assert len(results) == 1
        assert results[0].success is False
        assert "git clone failed" in results[0].error

    @patch("anteroom.services.space_bootstrap.subprocess.run")
    def test_clone_timeout(self, mock_run: object, tmp_path: Path) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("git", 120)
        results = clone_repos(["https://github.com/org/slow.git"], tmp_path)
        assert len(results) == 1
        assert results[0].success is False
        assert "timed out" in results[0].error


class TestInstallSpacePacks:
    def test_valid_pack_refs(self) -> None:
        from unittest.mock import MagicMock

        from anteroom.services.space_bootstrap import install_space_packs

        result = install_space_packs(MagicMock(), [], ["ns/pack1", "org/pack2"], Path("/tmp"))
        assert result == ["ns/pack1", "org/pack2"]

    def test_invalid_pack_ref_skipped(self) -> None:
        from unittest.mock import MagicMock

        from anteroom.services.space_bootstrap import install_space_packs

        result = install_space_packs(MagicMock(), [], ["invalid-no-slash"], Path("/tmp"))
        assert result == []
