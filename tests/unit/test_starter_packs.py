"""Tests for services/starter_packs.py."""

from __future__ import annotations

import sqlite3

import pytest

from anteroom.db import _SCHEMA, ThreadSafeConnection
from anteroom.services.starter_packs import (
    install_starter_packs,
    list_starter_packs,
)


@pytest.fixture()
def db() -> ThreadSafeConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    return ThreadSafeConnection(conn)


class TestListStarterPacks:
    def test_returns_all_available(self) -> None:
        result = list_starter_packs()
        assert len(result) == 2
        names = {p["name"] for p in result}
        assert "python-dev" in names
        assert "security-baseline" in names

    def test_each_has_required_fields(self) -> None:
        for pack in list_starter_packs():
            assert pack["name"]
            assert pack["namespace"] == "anteroom"
            assert pack["version"]
            assert pack["description"]


class TestInstallStarterPacks:
    def test_installs_all(self, db: ThreadSafeConnection) -> None:
        results = install_starter_packs(db)
        installed = [r for r in results if r["status"] == "installed"]
        assert len(installed) == 2

        # Verify in DB
        packs = db.execute("SELECT * FROM packs").fetchall()
        assert len(packs) == 2

        artifacts = db.execute("SELECT * FROM artifacts WHERE source = 'built_in'").fetchall()
        assert len(artifacts) > 0

    def test_idempotent_skips_same_version(self, db: ThreadSafeConnection) -> None:
        install_starter_packs(db)
        results = install_starter_packs(db)
        skipped = [r for r in results if r["status"] == "skipped"]
        assert len(skipped) == 2

    def test_updates_on_version_change(self, db: ThreadSafeConnection) -> None:
        install_starter_packs(db)

        # Manually change version in DB
        db.execute("UPDATE packs SET version = '0.0.1' WHERE name = 'python-dev'")
        db.commit()

        results = install_starter_packs(db)
        updated = [r for r in results if r["status"] == "updated"]
        assert len(updated) == 1
        assert updated[0]["name"] == "python-dev"

    def test_install_specific_names(self, db: ThreadSafeConnection) -> None:
        results = install_starter_packs(db, names=["python-dev"])
        assert len(results) == 1
        assert results[0]["name"] == "python-dev"
        assert results[0]["status"] == "installed"

        packs = db.execute("SELECT * FROM packs").fetchall()
        assert len(packs) == 1

    def test_install_nonexistent_name(self, db: ThreadSafeConnection) -> None:
        results = install_starter_packs(db, names=["nonexistent-pack"])
        assert len(results) == 1
        assert results[0]["status"] == "error"

    def test_artifacts_have_built_in_source(self, db: ThreadSafeConnection) -> None:
        install_starter_packs(db)
        artifacts = db.execute("SELECT * FROM artifacts").fetchall()
        for art in artifacts:
            assert art["source"] == "built_in"

    def test_pack_artifacts_linked(self, db: ThreadSafeConnection) -> None:
        install_starter_packs(db)
        links = db.execute("SELECT * FROM pack_artifacts").fetchall()
        assert len(links) > 0

        # Each link should reference a valid pack and artifact
        for link in links:
            pack = db.execute("SELECT id FROM packs WHERE id = ?", (link["pack_id"],)).fetchone()
            assert pack is not None
            art = db.execute("SELECT id FROM artifacts WHERE id = ?", (link["artifact_id"],)).fetchone()
            assert art is not None
