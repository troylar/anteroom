"""Tests for artifact health check engine."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from anteroom.db import _SCHEMA, ThreadSafeConnection
from anteroom.services import artifact_storage, pack_lock
from anteroom.services.artifact_health import (
    HealthIssue,
    HealthReport,
    HealthSeverity,
    check_bloat,
    check_config_overlay_conflicts,
    check_duplicate_content,
    check_empty_artifacts,
    check_lock_drift,
    check_malformed_artifacts,
    check_orphaned_artifacts,
    check_shadow_warnings,
    check_skill_name_collisions,
    fix_duplicate_content,
    run_health_check,
)


@pytest.fixture()
def db() -> ThreadSafeConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    return ThreadSafeConnection(conn)


def _create(db: ThreadSafeConnection, fqn: str, content: str, source: str = "local", **kw: object) -> dict:
    ns, atype, name = fqn[1:].split("/", 2)
    return artifact_storage.create_artifact(db, fqn, atype, ns, name, content, source=source, **kw)


# ---------------------------------------------------------------------------
# HealthReport dataclass
# ---------------------------------------------------------------------------


class TestHealthReport:
    def test_empty_report_is_healthy(self) -> None:
        r = HealthReport()
        assert r.healthy is True
        assert r.error_count == 0
        assert r.warn_count == 0
        assert r.info_count == 0

    def test_report_with_error_is_unhealthy(self) -> None:
        r = HealthReport(issues=[HealthIssue(HealthSeverity.ERROR, "test", "bad")])
        assert r.healthy is False
        assert r.error_count == 1

    def test_report_with_only_warnings_is_healthy(self) -> None:
        r = HealthReport(issues=[HealthIssue(HealthSeverity.WARN, "test", "meh")])
        assert r.healthy is True
        assert r.warn_count == 1

    def test_to_dict(self) -> None:
        r = HealthReport(
            issues=[HealthIssue(HealthSeverity.INFO, "bloat", "big")],
            artifact_count=5,
            total_size_bytes=1000,
            estimated_tokens=250,
        )
        d = r.to_dict()
        assert d["healthy"] is True
        assert d["artifact_count"] == 5
        assert d["info_count"] == 1
        assert len(d["issues"]) == 1
        assert d["issues"][0]["severity"] == "info"


# ---------------------------------------------------------------------------
# Config Overlay Conflicts
# ---------------------------------------------------------------------------


class TestConfigOverlayConflicts:
    def test_no_overlays_returns_empty(self, db: ThreadSafeConnection) -> None:
        assert check_config_overlay_conflicts(db) == []

    def test_single_overlay_no_conflict(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/safety", "safety:\n  approval_mode: ask\n")
        assert check_config_overlay_conflicts(db) == []

    def test_same_value_no_conflict(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/a", "safety:\n  approval_mode: ask\n", source="team")
        _create(db, "@project/config_overlay/b", "safety:\n  approval_mode: ask\n", source="project")
        assert check_config_overlay_conflicts(db) == []

    def test_different_values_reports_error(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/strict", "safety:\n  approval_mode: ask\n", source="team")
        _create(db, "@project/config_overlay/dev", "safety:\n  approval_mode: auto\n", source="project")
        issues = check_config_overlay_conflicts(db)
        assert len(issues) == 1
        assert issues[0].severity == HealthSeverity.ERROR
        assert issues[0].category == "config_conflict"
        assert "approval_mode" in issues[0].message

    def test_nested_config_conflict(self, db: ThreadSafeConnection) -> None:
        _create(db, "@a/config_overlay/x", "ai:\n  timeout: 30\n", source="global")
        _create(db, "@b/config_overlay/y", "ai:\n  timeout: 60\n", source="project")
        issues = check_config_overlay_conflicts(db)
        assert len(issues) == 1
        assert "ai.timeout" in issues[0].message

    def test_winner_is_highest_precedence(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/a", "key: val1\n", source="team")
        _create(db, "@local/config_overlay/b", "key: val2\n", source="local")
        issues = check_config_overlay_conflicts(db)
        assert len(issues) == 1
        assert issues[0].details["winner_fqn"] == "@local/config_overlay/b"

    def test_invalid_yaml_content_skipped(self, db: ThreadSafeConnection) -> None:
        _create(db, "@a/config_overlay/bad", "not: valid: yaml: [", source="global")
        _create(db, "@b/config_overlay/good", "key: val\n", source="project")
        issues = check_config_overlay_conflicts(db)
        assert issues == []


# ---------------------------------------------------------------------------
# Skill Name Collisions
# ---------------------------------------------------------------------------


class TestSkillNameCollisions:
    def test_no_skills_returns_empty(self, db: ThreadSafeConnection) -> None:
        assert check_skill_name_collisions(db) == []

    def test_unique_names_no_collision(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/greet", "Hello")
        _create(db, "@core/skill/commit", "Commit helper")
        assert check_skill_name_collisions(db) == []

    def test_same_name_different_ns_reports_collision(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/commit", "Built-in commit", source="built_in")
        _create(db, "@custom/skill/commit", "Custom commit", source="local")
        issues = check_skill_name_collisions(db)
        assert len(issues) == 1
        assert issues[0].severity == HealthSeverity.WARN
        assert issues[0].category == "skill_collision"
        assert issues[0].details["active_fqn"] == "@custom/skill/commit"

    def test_three_way_collision(self, db: ThreadSafeConnection) -> None:
        _create(db, "@a/skill/deploy", "A", source="built_in")
        _create(db, "@b/skill/deploy", "B", source="team")
        _create(db, "@c/skill/deploy", "C", source="local")
        issues = check_skill_name_collisions(db)
        assert len(issues) == 1
        assert len(issues[0].details["shadowed"]) == 2


# ---------------------------------------------------------------------------
# Shadow Warnings
# ---------------------------------------------------------------------------


class TestShadowWarnings:
    def test_no_artifacts_returns_empty(self, db: ThreadSafeConnection) -> None:
        assert check_shadow_warnings(db) == []

    def test_single_artifact_no_shadow(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/rule/security", "Be secure")
        assert check_shadow_warnings(db) == []

    def test_same_type_name_different_source_reports_shadow(self, db: ThreadSafeConnection) -> None:
        _create(db, "@builtin/rule/security", "Default rules", source="built_in")
        _create(db, "@local/rule/security", "Override rules", source="local")
        issues = check_shadow_warnings(db)
        assert len(issues) == 1
        assert issues[0].severity == HealthSeverity.INFO
        assert issues[0].category == "shadow"
        assert "@local/rule/security" in issues[0].message
        assert "@builtin/rule/security" in issues[0].message

    def test_different_types_same_name_no_shadow(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/greet", "Skill content")
        _create(db, "@core/rule/greet", "Rule content")
        assert check_shadow_warnings(db) == []


# ---------------------------------------------------------------------------
# Empty Artifacts
# ---------------------------------------------------------------------------


class TestEmptyArtifacts:
    def test_no_artifacts_returns_empty(self, db: ThreadSafeConnection) -> None:
        assert check_empty_artifacts(db) == []

    def test_normal_content_passes(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/rule/security", "This is a rule with enough words to pass the minimum threshold easily")
        assert check_empty_artifacts(db) == []

    def test_short_content_flagged(self, db: ThreadSafeConnection) -> None:
        _create(db, "@proj/instruction/notes", "Just a few words")
        issues = check_empty_artifacts(db)
        assert len(issues) == 1
        assert issues[0].severity == HealthSeverity.WARN
        assert issues[0].category == "empty_artifact"
        assert issues[0].details["word_count"] == 4

    def test_empty_string_flagged(self, db: ThreadSafeConnection) -> None:
        _create(db, "@proj/instruction/blank", "")
        issues = check_empty_artifacts(db)
        assert len(issues) == 1
        assert issues[0].details["word_count"] == 0

    def test_exactly_ten_words_passes(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/rule/borderline", "one two three four five six seven eight nine ten")
        assert check_empty_artifacts(db) == []


# ---------------------------------------------------------------------------
# Malformed Artifacts
# ---------------------------------------------------------------------------


class TestMalformedArtifacts:
    def test_valid_artifact_passes(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/greet", "Hello world, this is a valid artifact with enough content")
        assert check_malformed_artifacts(db) == []

    def test_invalid_yaml_in_config_overlay(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/bad", "not: valid: yaml: {{{")
        issues = check_malformed_artifacts(db)
        yaml_issues = [i for i in issues if "YAML" in i.message]
        assert len(yaml_issues) == 1
        assert yaml_issues[0].severity == HealthSeverity.ERROR

    def test_non_mapping_config_overlay(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/list", "- item1\n- item2\n")
        issues = check_malformed_artifacts(db)
        mapping_issues = [i for i in issues if "not a YAML mapping" in i.message]
        assert len(mapping_issues) == 1
        assert mapping_issues[0].severity == HealthSeverity.WARN

    def test_valid_config_overlay_passes(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/good", "safety:\n  approval_mode: ask\n")
        issues = check_malformed_artifacts(db)
        yaml_issues = [i for i in issues if i.category == "malformed" and "YAML" in i.message]
        assert yaml_issues == []

    def test_mcp_server_yaml_validated(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/mcp_server/bad", "invalid yaml {{")
        issues = check_malformed_artifacts(db)
        yaml_issues = [i for i in issues if "YAML" in i.message]
        assert len(yaml_issues) >= 1


# ---------------------------------------------------------------------------
# Lock Drift
# ---------------------------------------------------------------------------


class TestLockDrift:
    def test_no_project_dir_returns_empty(self, db: ThreadSafeConnection) -> None:
        assert check_lock_drift(db, None) == []

    def test_no_lock_file_reports_warning(self, db: ThreadSafeConnection, tmp_path: Path) -> None:
        issues = check_lock_drift(db, tmp_path)
        assert len(issues) == 1
        assert issues[0].severity == HealthSeverity.WARN
        assert "not found" in issues[0].message.lower()

    def test_valid_lock_returns_empty(self, db: ThreadSafeConnection, tmp_path: Path) -> None:
        _create(db, "@ns/skill/greet", "Hello!")
        db.execute(
            "INSERT INTO packs (id, name, namespace, version, installed_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pid", "test-pack", "ns", "1.0.0", "2024-01-01", "2024-01-01"),
        )
        art = artifact_storage.get_artifact_by_fqn(db, "@ns/skill/greet")
        db.execute(
            "INSERT INTO pack_artifacts (pack_id, artifact_id) VALUES (?, ?)",
            ("pid", art["id"]),
        )
        db.commit()
        lock_data = pack_lock.generate_lock(db)
        pack_lock.write_lock(tmp_path, lock_data)
        issues = check_lock_drift(db, tmp_path)
        assert issues == []

    def test_hash_mismatch_reports_error(self, db: ThreadSafeConnection, tmp_path: Path) -> None:
        _create(db, "@ns/skill/greet", "Hello!")
        db.execute(
            "INSERT INTO packs (id, name, namespace, version, installed_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pid", "test-pack", "ns", "1.0.0", "2024-01-01", "2024-01-01"),
        )
        art = artifact_storage.get_artifact_by_fqn(db, "@ns/skill/greet")
        db.execute(
            "INSERT INTO pack_artifacts (pack_id, artifact_id) VALUES (?, ?)",
            ("pid", art["id"]),
        )
        db.commit()
        lock_data = pack_lock.generate_lock(db)
        lock_data["packs"][0]["artifacts"][0]["content_hash"] = "deadbeef" * 8
        pack_lock.write_lock(tmp_path, lock_data)
        issues = check_lock_drift(db, tmp_path)
        error_issues = [i for i in issues if i.severity == HealthSeverity.ERROR]
        assert len(error_issues) == 1
        assert "mismatch" in error_issues[0].message.lower()


# ---------------------------------------------------------------------------
# Orphaned Artifacts
# ---------------------------------------------------------------------------


class TestOrphanedArtifacts:
    def test_no_packs_returns_empty(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/greet", "Hello")
        assert check_orphaned_artifacts(db) == []

    def test_linked_artifact_not_orphaned(self, db: ThreadSafeConnection) -> None:
        art = _create(db, "@ns/skill/greet", "Hello", source="global")
        db.execute(
            "INSERT INTO packs (id, name, namespace, version, installed_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pid", "test-pack", "ns", "1.0.0", "2024-01-01", "2024-01-01"),
        )
        db.execute("INSERT INTO pack_artifacts (pack_id, artifact_id) VALUES (?, ?)", ("pid", art["id"]))
        db.commit()
        assert check_orphaned_artifacts(db) == []

    def test_unlinked_global_artifact_flagged(self, db: ThreadSafeConnection) -> None:
        _create(db, "@ns/skill/greet", "Hello", source="global")
        db.execute(
            "INSERT INTO packs (id, name, namespace, version, installed_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pid", "other-pack", "ns", "1.0.0", "2024-01-01", "2024-01-01"),
        )
        db.commit()
        issues = check_orphaned_artifacts(db)
        assert len(issues) == 1
        assert issues[0].category == "orphaned"

    def test_builtin_artifact_not_flagged(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/greet", "Hello", source="built_in")
        db.execute(
            "INSERT INTO packs (id, name, namespace, version, installed_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pid", "other-pack", "ns", "1.0.0", "2024-01-01", "2024-01-01"),
        )
        db.commit()
        assert check_orphaned_artifacts(db) == []

    def test_local_artifact_not_flagged(self, db: ThreadSafeConnection) -> None:
        _create(db, "@me/skill/greet", "Hello", source="local")
        db.execute(
            "INSERT INTO packs (id, name, namespace, version, installed_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pid", "other-pack", "ns", "1.0.0", "2024-01-01", "2024-01-01"),
        )
        db.commit()
        assert check_orphaned_artifacts(db) == []


# ---------------------------------------------------------------------------
# Duplicate Content
# ---------------------------------------------------------------------------


class TestDuplicateContent:
    def test_no_duplicates_returns_empty(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/a", "Unique content A")
        _create(db, "@core/skill/b", "Unique content B")
        assert check_duplicate_content(db) == []

    def test_identical_content_detected(self, db: ThreadSafeConnection) -> None:
        _create(db, "@ns1/rule/security", "Be secure always", source="team")
        _create(db, "@ns2/rule/security", "Be secure always", source="project")
        issues = check_duplicate_content(db)
        assert len(issues) == 1
        assert issues[0].severity == HealthSeverity.WARN
        assert issues[0].fixable is True
        assert len(issues[0].details["artifacts"]) == 2

    def test_single_artifact_no_duplicate(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/only", "Solo content")
        assert check_duplicate_content(db) == []


# ---------------------------------------------------------------------------
# Fix Duplicate Content
# ---------------------------------------------------------------------------


class TestFixDuplicateContent:
    def test_no_duplicates_deletes_nothing(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/a", "Unique A")
        _create(db, "@core/skill/b", "Unique B")
        assert fix_duplicate_content(db) == 0
        assert len(artifact_storage.list_artifacts(db)) == 2

    def test_removes_lower_precedence_duplicate(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/rule/sec", "Same content", source="team")
        _create(db, "@local/rule/sec", "Same content", source="local")
        deleted = fix_duplicate_content(db)
        assert deleted == 1
        remaining = artifact_storage.list_artifacts(db)
        assert len(remaining) == 1
        assert remaining[0]["fqn"] == "@local/rule/sec"

    def test_three_duplicates_keeps_highest(self, db: ThreadSafeConnection) -> None:
        _create(db, "@a/rule/x", "Same", source="built_in")
        _create(db, "@b/rule/x", "Same", source="team")
        _create(db, "@c/rule/x", "Same", source="local")
        deleted = fix_duplicate_content(db)
        assert deleted == 2
        remaining = artifact_storage.list_artifacts(db)
        assert len(remaining) == 1
        assert remaining[0]["source"] == "local"


# ---------------------------------------------------------------------------
# Bloat
# ---------------------------------------------------------------------------


class TestBloat:
    def test_no_artifacts_returns_empty(self, db: ThreadSafeConnection) -> None:
        assert check_bloat(db) == []

    def test_reports_artifact_stats(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/a", "A" * 100)
        _create(db, "@core/skill/b", "B" * 200)
        issues = check_bloat(db)
        assert len(issues) == 1
        assert issues[0].severity == HealthSeverity.INFO
        assert issues[0].category == "bloat"
        assert issues[0].details["artifact_count"] == 2
        assert issues[0].details["total_size_bytes"] == 300

    def test_top_by_size_ordered(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/small", "x" * 10)
        _create(db, "@core/skill/big", "y" * 500)
        _create(db, "@core/skill/medium", "z" * 100)
        issues = check_bloat(db)
        top = issues[0].details["top_by_size"]
        assert top[0]["fqn"] == "@core/skill/big"


# ---------------------------------------------------------------------------
# Run Health Check (orchestrator)
# ---------------------------------------------------------------------------


class TestRunHealthCheck:
    def test_empty_db_healthy(self, db: ThreadSafeConnection) -> None:
        report = run_health_check(db)
        assert report.healthy is True
        assert report.artifact_count == 0

    def test_reports_all_check_categories(self, db: ThreadSafeConnection) -> None:
        _create(db, "@team/config_overlay/a", "key: val1\n", source="team")
        _create(db, "@local/config_overlay/b", "key: val2\n", source="local")
        _create(db, "@core/skill/commit", "Do commit", source="built_in")
        _create(db, "@custom/skill/commit", "Custom commit", source="local")
        report = run_health_check(db)
        categories = {i.category for i in report.issues}
        assert "config_conflict" in categories
        assert "skill_collision" in categories

    def test_fix_mode_removes_duplicates(self, db: ThreadSafeConnection) -> None:
        _create(db, "@a/rule/dup", "Same text here", source="team")
        _create(db, "@b/rule/dup", "Same text here", source="local")
        report = run_health_check(db, fix=True)
        fix_issues = [i for i in report.issues if i.category == "fix_applied"]
        assert len(fix_issues) == 1
        assert artifact_storage.list_artifacts(db).__len__() == 1

    def test_artifact_count_and_size(self, db: ThreadSafeConnection) -> None:
        _create(db, "@core/skill/a", "Hello world content here for testing")
        report = run_health_check(db)
        assert report.artifact_count == 1
        assert report.total_size_bytes == len("Hello world content here for testing")
        assert report.estimated_tokens == report.total_size_bytes // 4

    def test_to_dict_json_serializable(self, db: ThreadSafeConnection) -> None:
        import json

        _create(db, "@core/skill/a", "Some content for testing the serialization")
        report = run_health_check(db)
        d = report.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_project_dir_enables_lock_check(self, db: ThreadSafeConnection, tmp_path: Path) -> None:
        report = run_health_check(db, project_dir=tmp_path)
        lock_issues = [i for i in report.issues if i.category == "lock_drift"]
        assert len(lock_issues) == 1
