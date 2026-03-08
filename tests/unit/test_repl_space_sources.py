"""Tests for CLI /space sources, /space link-source, /space unlink-source commands."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from anteroom.db import ThreadSafeConnection


def _make_db() -> ThreadSafeConnection:
    """Create an in-memory DB with required tables."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "CREATE TABLE spaces (id TEXT PRIMARY KEY, name TEXT, file_path TEXT, "
        "file_hash TEXT DEFAULT '', last_loaded_at TEXT, created_at TEXT, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE sources (id TEXT PRIMARY KEY, type TEXT, title TEXT, content TEXT, "
        "mime_type TEXT, filename TEXT, url TEXT, storage_path TEXT, size_bytes INTEGER, "
        "content_hash TEXT, user_id TEXT, user_display_name TEXT, created_at TEXT, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE source_groups (id TEXT PRIMARY KEY, name TEXT, description TEXT DEFAULT '', "
        "user_id TEXT, user_display_name TEXT, created_at TEXT, updated_at TEXT)"
    )
    conn.execute("CREATE TABLE source_group_members (group_id TEXT, source_id TEXT, PRIMARY KEY (group_id, source_id))")
    conn.execute(
        "CREATE TABLE space_sources ("
        "space_id TEXT NOT NULL, source_id TEXT, group_id TEXT, tag_filter TEXT, "
        "created_at TEXT NOT NULL, "
        "FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE CASCADE, "
        "CHECK ("
        "  (source_id IS NOT NULL AND group_id IS NULL AND tag_filter IS NULL) OR "
        "  (source_id IS NULL AND group_id IS NOT NULL AND tag_filter IS NULL) OR "
        "  (source_id IS NULL AND group_id IS NULL AND tag_filter IS NOT NULL)"
        "))"
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(f"INSERT INTO spaces VALUES ('sp1', 'myspace', '/s.yaml', '', '', '{now}', '{now}')")
    conn.execute(
        f"INSERT INTO sources VALUES ('src1', 'text', 'Doc Alpha', 'content', 'text/plain', "
        f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{now}', '{now}')"
    )
    conn.execute(
        f"INSERT INTO sources VALUES ('src2', 'file', 'Report Beta', 'content2', 'text/plain', "
        f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{now}', '{now}')"
    )
    conn.commit()
    return ThreadSafeConnection(conn)


def test_space_sources_lists_direct_links() -> None:
    """'/space sources' lists directly-linked sources."""
    from anteroom.services.storage import get_direct_space_source_links, link_source_to_space

    db = _make_db()
    link_source_to_space(db, "sp1", source_id="src1")
    link_source_to_space(db, "sp1", source_id="src2")

    linked = get_direct_space_source_links(db, "sp1")
    titles = {s["title"] for s in linked}
    assert titles == {"Doc Alpha", "Report Beta"}


def test_space_sources_empty_when_no_links() -> None:
    """'/space sources' returns empty when no sources linked."""
    from anteroom.services.storage import get_direct_space_source_links

    db = _make_db()
    assert get_direct_space_source_links(db, "sp1") == []


def test_link_source_by_exact_title() -> None:
    """'/space link-source' matches source by exact title."""
    from anteroom.services.storage import get_direct_space_source_links, link_source_to_space, list_sources

    db = _make_db()
    all_srcs = list_sources(db)
    match = None
    for s in all_srcs:
        if s.get("title", "").lower() == "doc alpha":
            match = s
            break
    assert match is not None
    link_source_to_space(db, "sp1", source_id=match["id"])

    linked = get_direct_space_source_links(db, "sp1")
    assert len(linked) == 1
    assert linked[0]["title"] == "Doc Alpha"


def test_link_source_by_partial_title() -> None:
    """'/space link-source' matches source by partial title."""
    from anteroom.services.storage import list_sources

    db = _make_db()
    all_srcs = list_sources(db)
    query = "alpha"
    match = None
    for s in all_srcs:
        if query.lower() in s.get("title", "").lower():
            match = s
            break
    assert match is not None
    assert match["title"] == "Doc Alpha"


def test_link_source_by_id() -> None:
    """'/space link-source' matches source by exact ID."""
    from anteroom.services.storage import list_sources

    db = _make_db()
    all_srcs = list_sources(db)
    match = None
    for s in all_srcs:
        if s["id"] == "src1":
            match = s
            break
    assert match is not None
    assert match["title"] == "Doc Alpha"


def test_unlink_source_removes_link() -> None:
    """'/space unlink-source' removes the direct link."""
    from anteroom.services.storage import (
        get_direct_space_source_links,
        link_source_to_space,
        unlink_source_from_space,
    )

    db = _make_db()
    link_source_to_space(db, "sp1", source_id="src1")
    link_source_to_space(db, "sp1", source_id="src2")
    assert len(get_direct_space_source_links(db, "sp1")) == 2

    unlink_source_from_space(db, "sp1", source_id="src1")
    linked = get_direct_space_source_links(db, "sp1")
    assert len(linked) == 1
    assert linked[0]["id"] == "src2"


def test_unlink_source_not_linked_returns_true() -> None:
    """Unlinking a source that isn't linked still returns True (DELETE succeeds with 0 rows)."""
    from anteroom.services.storage import unlink_source_from_space

    db = _make_db()
    result = unlink_source_from_space(db, "sp1", source_id="src1")
    assert result is True


def test_direct_links_exclude_group_links() -> None:
    """get_direct_space_source_links excludes group-linked sources."""
    from anteroom.services.storage import get_direct_space_source_links, link_source_to_space

    db = _make_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(f"INSERT INTO source_groups VALUES ('g1', 'my-group', '', NULL, NULL, '{now}', '{now}')")
    db.execute("INSERT INTO source_group_members VALUES ('g1', 'src2')")
    db.commit()

    link_source_to_space(db, "sp1", source_id="src1")
    link_source_to_space(db, "sp1", group_id="g1")

    direct = get_direct_space_source_links(db, "sp1")
    assert len(direct) == 1
    assert direct[0]["id"] == "src1"
    assert direct[0]["title"] == "Doc Alpha"


def test_list_sources_limit_zero_returns_all() -> None:
    """list_sources with limit=0 returns all sources (no pagination cap)."""
    from anteroom.services.storage import list_sources

    db = _make_db()
    # Add more sources to exceed default limit
    now = datetime.now(timezone.utc).isoformat()
    for i in range(5):
        db.execute(
            f"INSERT INTO sources VALUES ('extra{i}', 'text', 'Extra {i}', 'c', 'text/plain', "
            f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{now}', '{now}')"
        )
    db.commit()

    # Default limit returns up to 100 (we have 7 total)
    default = list_sources(db)
    assert len(default) == 7

    # limit=0 also returns all
    unlimited = list_sources(db, limit=0)
    assert len(unlimited) == 7


def test_partial_match_multiple_candidates() -> None:
    """When multiple sources match a partial query, all should be candidates."""
    from anteroom.services.storage import list_sources

    db = _make_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        f"INSERT INTO sources VALUES ('src3', 'text', 'Q1 Report', 'c', 'text/plain', "
        f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{now}', '{now}')"
    )
    db.execute(
        f"INSERT INTO sources VALUES ('src4', 'text', 'Q2 Report', 'c', 'text/plain', "
        f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{now}', '{now}')"
    )
    db.commit()

    all_srcs = list_sources(db, limit=0)
    query = "report"
    candidates = [s for s in all_srcs if query.lower() in s.get("title", "").lower()]
    # Should match "Report Beta", "Q1 Report", "Q2 Report"
    assert len(candidates) == 3
    titles = {c["title"] for c in candidates}
    assert titles == {"Report Beta", "Q1 Report", "Q2 Report"}


def test_exact_title_duplicate_disambiguation() -> None:
    """When multiple sources share the exact same title, disambiguation is required."""
    from anteroom.services.storage import list_sources

    db = _make_db()
    now = datetime.now(timezone.utc).isoformat()
    # Two sources with identical titles
    db.execute(
        f"INSERT INTO sources VALUES ('src5', 'text', 'Quarterly Report', 'v1', 'text/plain', "
        f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{now}', '{now}')"
    )
    db.execute(
        f"INSERT INTO sources VALUES ('src6', 'text', 'Quarterly Report', 'v2', 'text/plain', "
        f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{now}', '{now}')"
    )
    db.commit()

    all_srcs = list_sources(db, limit=0)
    query = "quarterly report"
    # Exact title match should find both
    exact = [s for s in all_srcs if s.get("title", "").lower() == query.lower()]
    assert len(exact) == 2
    ids = {s["id"] for s in exact}
    assert ids == {"src5", "src6"}

    # ID match is always unambiguous
    id_match = [s for s in all_srcs if s["id"] == "src5"]
    assert len(id_match) == 1
    assert id_match[0]["content"] == "v1"
