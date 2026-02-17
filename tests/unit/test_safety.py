"""Tests for tools/safety.py detection logic."""

from __future__ import annotations

from anteroom.tools.safety import check_bash_command, check_write_path


class TestCheckBashCommand:
    def test_rm_triggers(self) -> None:
        v = check_bash_command("rm -rf /tmp/test")
        assert v.needs_approval
        assert "rm" in v.details.get("matched_pattern", "")

    def test_rmdir_triggers(self) -> None:
        v = check_bash_command("rmdir my_dir")
        assert v.needs_approval

    def test_git_push_force_triggers(self) -> None:
        v = check_bash_command("git push --force origin main")
        assert v.needs_approval

    def test_git_push_f_triggers(self) -> None:
        v = check_bash_command("git push -f origin main")
        assert v.needs_approval

    def test_git_reset_hard_triggers(self) -> None:
        v = check_bash_command("git reset --hard HEAD~1")
        assert v.needs_approval

    def test_git_clean_triggers(self) -> None:
        v = check_bash_command("git clean -fd")
        assert v.needs_approval

    def test_git_checkout_dot_triggers(self) -> None:
        v = check_bash_command("git checkout .")
        assert v.needs_approval

    def test_drop_table_triggers(self) -> None:
        v = check_bash_command("sqlite3 db.sqlite 'DROP TABLE users'")
        assert v.needs_approval

    def test_drop_database_triggers(self) -> None:
        v = check_bash_command("mysql -e 'DROP DATABASE mydb'")
        assert v.needs_approval

    def test_truncate_triggers(self) -> None:
        v = check_bash_command("psql -c 'TRUNCATE users'")
        assert v.needs_approval

    def test_redirect_dev_triggers(self) -> None:
        v = check_bash_command("echo '' > /dev/sda")
        assert v.needs_approval

    def test_chmod_777_triggers(self) -> None:
        v = check_bash_command("chmod 777 /etc/config")
        assert v.needs_approval

    def test_kill_9_triggers(self) -> None:
        v = check_bash_command("kill -9 1234")
        assert v.needs_approval

    def test_safe_command_passes(self) -> None:
        v = check_bash_command("echo hello")
        assert not v.needs_approval

    def test_ls_passes(self) -> None:
        v = check_bash_command("ls -la")
        assert not v.needs_approval

    def test_word_boundary_myrmdir(self) -> None:
        v = check_bash_command("myrmdir something")
        assert not v.needs_approval

    def test_whitespace_normalization(self) -> None:
        v = check_bash_command("rm\t-rf /tmp/test")
        assert v.needs_approval

    def test_custom_pattern_string(self) -> None:
        v = check_bash_command("docker system prune -af", custom_patterns=["docker system prune"])
        assert v.needs_approval

    def test_custom_pattern_regex(self) -> None:
        v = check_bash_command("kubectl delete pod foo", custom_patterns=[r"kubectl\s+delete"])
        assert v.needs_approval

    def test_custom_pattern_no_match(self) -> None:
        v = check_bash_command("docker ps", custom_patterns=["docker system prune"])
        assert not v.needs_approval

    def test_empty_command(self) -> None:
        v = check_bash_command("")
        assert not v.needs_approval

    def test_none_like_command(self) -> None:
        v = check_bash_command("  ")
        assert not v.needs_approval

    def test_invalid_regex_fallback_to_substring(self) -> None:
        # Invalid regex (unbalanced bracket) should fall back to substring match
        v = check_bash_command("danger[zone command", custom_patterns=["danger[zone"])
        assert v.needs_approval

    def test_invalid_regex_fallback_no_match(self) -> None:
        v = check_bash_command("safe command", custom_patterns=["danger[zone"])
        assert not v.needs_approval

    def test_verdict_fields(self) -> None:
        v = check_bash_command("rm -rf /")
        assert v.tool_name == "bash"
        assert "rm" in v.reason.lower()
        assert "command" in v.details


class TestCheckWritePath:
    def test_dotenv_triggers(self) -> None:
        v = check_write_path(".env", "/home/user/project")
        assert v.needs_approval

    def test_ssh_dir_triggers(self) -> None:
        v = check_write_path("/home/user/.ssh/id_rsa", "/tmp")
        assert v.needs_approval

    def test_safe_path_passes(self) -> None:
        v = check_write_path("src/foo.py", "/home/user/project")
        assert not v.needs_approval

    def test_custom_sensitive_path(self) -> None:
        v = check_write_path("secrets.json", "/home/user/project", sensitive_paths=["secrets.json"])
        assert v.needs_approval

    def test_custom_sensitive_not_matched(self) -> None:
        v = check_write_path("data.json", "/home/user/project", sensitive_paths=["secrets.json"])
        assert not v.needs_approval

    def test_empty_path(self) -> None:
        v = check_write_path("", "/tmp")
        assert not v.needs_approval

    def test_verdict_fields(self) -> None:
        v = check_write_path(".env", "/tmp")
        assert v.tool_name == "write_file"
        assert "sensitive" in v.reason.lower()

    def test_aws_credentials_triggers(self) -> None:
        v = check_write_path(".aws/credentials", "/home/user/project")
        assert v.needs_approval

    def test_gnupg_triggers(self) -> None:
        v = check_write_path(".gnupg/pubring.gpg", "/home/user/project")
        assert v.needs_approval

    def test_config_gcloud_triggers(self) -> None:
        v = check_write_path(".config/gcloud/creds.json", "/home/user/project")
        assert v.needs_approval

    def test_tilde_prefix_custom_sensitive(self) -> None:
        v = check_write_path(".my_secret/key", "/home/user/project", sensitive_paths=["~/.my_secret"])
        assert v.needs_approval

    def test_path_traversal_into_sensitive(self) -> None:
        v = check_write_path("../../.ssh/id_rsa", "/home/user/project/deep/dir")
        assert v.needs_approval

    def test_safe_command_verdict_tool_name(self) -> None:
        v = check_bash_command("echo hello")
        assert v.tool_name == "bash"

    def test_newline_normalization(self) -> None:
        v = check_bash_command("rm\n-rf /tmp/test")
        assert v.needs_approval
