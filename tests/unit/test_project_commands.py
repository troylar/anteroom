"""Tests for project management: storage CRUD and CLI command helpers."""

from __future__ import annotations

import sqlite3

import pytest

from anteroom.db import _FTS_SCHEMA, _FTS_TRIGGERS, _SCHEMA, ThreadSafeConnection
from anteroom.services.storage import (
    count_project_conversations,
    create_conversation,
    create_project,
    delete_project,
    get_project,
    get_project_by_name,
    list_projects,
    update_conversation_project,
    update_project,
)


@pytest.fixture()
def db() -> ThreadSafeConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    try:
        conn.executescript(_FTS_SCHEMA)
        conn.executescript(_FTS_TRIGGERS)
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return ThreadSafeConnection(conn)


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


class TestCreateProject:
    def test_returns_dict_with_all_fields(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="My Project")
        assert proj["name"] == "My Project"
        assert proj["instructions"] == ""
        assert proj["model"] is None
        assert "id" in proj
        assert "created_at" in proj
        assert "updated_at" in proj

    def test_with_instructions_and_model(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Dev", instructions="Do stuff", model="gpt-4o")
        assert proj["instructions"] == "Do stuff"
        assert proj["model"] == "gpt-4o"

    def test_with_user_identity(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P", user_id="u1", user_display_name="Alice")
        assert proj["user_id"] == "u1"
        assert proj["user_display_name"] == "Alice"

    def test_persists_in_db(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Persisted")
        fetched = get_project(db, proj["id"])
        assert fetched is not None
        assert fetched["name"] == "Persisted"


class TestGetProject:
    def test_returns_none_for_missing(self, db: ThreadSafeConnection) -> None:
        assert get_project(db, "nonexistent-id") is None

    def test_returns_project(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Found")
        result = get_project(db, proj["id"])
        assert result is not None
        assert result["id"] == proj["id"]


class TestGetProjectByName:
    def test_exact_match(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Alpha")
        result = get_project_by_name(db, "Alpha")
        assert result is not None
        assert result["id"] == proj["id"]

    def test_case_insensitive(self, db: ThreadSafeConnection) -> None:
        create_project(db, name="MyProject")
        assert get_project_by_name(db, "myproject") is not None
        assert get_project_by_name(db, "MYPROJECT") is not None
        assert get_project_by_name(db, "MyProject") is not None

    def test_returns_none_when_not_found(self, db: ThreadSafeConnection) -> None:
        assert get_project_by_name(db, "ghost") is None


class TestListProjects:
    def test_empty(self, db: ThreadSafeConnection) -> None:
        assert list_projects(db) == []

    def test_returns_all_ordered_by_updated(self, db: ThreadSafeConnection) -> None:
        create_project(db, name="First")
        create_project(db, name="Second")
        projects = list_projects(db)
        assert len(projects) == 2
        assert projects[0]["name"] == "Second"  # most recently updated first


class TestUpdateProject:
    def test_update_name(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Old")
        updated = update_project(db, proj["id"], name="New")
        assert updated is not None
        assert updated["name"] == "New"

    def test_update_instructions(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P", instructions="before")
        updated = update_project(db, proj["id"], instructions="after")
        assert updated is not None
        assert updated["instructions"] == "after"

    def test_update_model(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P", model="old-model")
        updated = update_project(db, proj["id"], model="new-model")
        assert updated is not None
        assert updated["model"] == "new-model"

    def test_clear_model(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P", model="some-model")
        updated = update_project(db, proj["id"], model=None)
        assert updated is not None
        assert updated["model"] is None

    def test_returns_none_for_missing(self, db: ThreadSafeConnection) -> None:
        assert update_project(db, "nonexistent", name="X") is None

    def test_no_changes_still_updates_timestamp(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P")
        updated = update_project(db, proj["id"])
        assert updated is not None
        assert updated["updated_at"] >= proj["updated_at"]


class TestDeleteProject:
    def test_deletes_existing(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Doomed")
        assert delete_project(db, proj["id"]) is True
        assert get_project(db, proj["id"]) is None

    def test_returns_false_for_missing(self, db: ThreadSafeConnection) -> None:
        assert delete_project(db, "nonexistent") is False


# ---------------------------------------------------------------------------
# Conversation-project linking
# ---------------------------------------------------------------------------


class TestUpdateConversationProject:
    def test_set_project(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P")
        conv = create_conversation(db)
        result = update_conversation_project(db, conv["id"], proj["id"])
        assert result is not None
        assert result["project_id"] == proj["id"]

    def test_clear_project(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P")
        conv = create_conversation(db, project_id=proj["id"])
        result = update_conversation_project(db, conv["id"], None)
        assert result is not None
        assert result["project_id"] is None

    def test_returns_none_for_missing_conversation(self, db: ThreadSafeConnection) -> None:
        result = update_conversation_project(db, "nonexistent", None)
        assert result is None


class TestCountProjectConversations:
    def test_zero_when_no_conversations(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Empty")
        assert count_project_conversations(db, proj["id"]) == 0

    def test_counts_linked_conversations(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Busy")
        create_conversation(db, project_id=proj["id"])
        create_conversation(db, project_id=proj["id"])
        create_conversation(db)  # unlinked
        assert count_project_conversations(db, proj["id"]) == 2


# ---------------------------------------------------------------------------
# Create conversation with project_id
# ---------------------------------------------------------------------------


class TestCreateConversationWithProject:
    def test_project_id_set(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="P")
        conv = create_conversation(db, project_id=proj["id"])
        assert conv["project_id"] == proj["id"]

    def test_project_id_none_by_default(self, db: ThreadSafeConnection) -> None:
        conv = create_conversation(db)
        assert conv["project_id"] is None


# ---------------------------------------------------------------------------
# Project cascade: deleting project nullifies conversations
# ---------------------------------------------------------------------------


class TestProjectDeleteCascade:
    def test_delete_project_nullifies_conversations(self, db: ThreadSafeConnection) -> None:
        proj = create_project(db, name="Cascade")
        conv = create_conversation(db, project_id=proj["id"])
        delete_project(db, proj["id"])
        from anteroom.services.storage import get_conversation

        refreshed = get_conversation(db, conv["id"])
        assert refreshed is not None
        assert refreshed["project_id"] is None  # ON DELETE SET NULL
