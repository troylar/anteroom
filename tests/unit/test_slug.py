"""Tests for slug generation and uniqueness."""

from __future__ import annotations

import re
import sqlite3

import pytest

from anteroom.db import _SCHEMA, ThreadSafeConnection
from anteroom.services.slug import ADJECTIVES, COLORS, NOUNS, generate_slug, suggest_unique_slug


@pytest.fixture()
def db() -> ThreadSafeConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    return ThreadSafeConnection(conn)


class TestGenerateSlug:
    def test_format(self, db: ThreadSafeConnection) -> None:
        slug = generate_slug(db)
        parts = slug.split("-")
        assert len(parts) == 3
        assert parts[0] in ADJECTIVES
        assert parts[1] in COLORS
        assert parts[2] in NOUNS

    def test_unique_across_calls(self, db: ThreadSafeConnection) -> None:
        slugs = {generate_slug(db) for _ in range(50)}
        # With ~270K combos, 50 calls should all be unique
        assert len(slugs) == 50

    def test_avoids_collision(self, db: ThreadSafeConnection) -> None:
        slug1 = generate_slug(db)
        # Insert it into the DB to create a collision scenario
        db.execute(
            "INSERT INTO conversations (id, title, slug, type, created_at, updated_at) "
            "VALUES ('id1', 'test', ?, 'chat', '2024-01-01', '2024-01-01')",
            (slug1,),
        )
        db.commit()
        # Next slug should be different
        slug2 = generate_slug(db)
        assert slug2 != slug1

    def test_matches_pattern(self, db: ThreadSafeConnection) -> None:
        slug = generate_slug(db)
        assert re.match(r"^[a-z]+-[a-z]+-[a-z]+$", slug)


class TestSuggestUniqueSlug:
    def test_available_returns_none(self, db: ThreadSafeConnection) -> None:
        result = suggest_unique_slug(db, "my-project")
        assert result is None

    def test_taken_suggests_suffix(self, db: ThreadSafeConnection) -> None:
        db.execute(
            "INSERT INTO conversations (id, title, slug, type, created_at, updated_at) "
            "VALUES ('id1', 'test', 'my-project', 'chat', '2024-01-01', '2024-01-01')",
        )
        db.commit()
        result = suggest_unique_slug(db, "my-project")
        assert result == "my-project-2"

    def test_taken_with_suffix_increments(self, db: ThreadSafeConnection) -> None:
        for i, suffix in enumerate(["my-project", "my-project-2", "my-project-3"]):
            db.execute(
                "INSERT INTO conversations (id, title, slug, type, created_at, updated_at) "
                "VALUES (?, 'test', ?, 'chat', '2024-01-01', '2024-01-01')",
                (f"id{i}", suffix),
            )
        db.commit()
        result = suggest_unique_slug(db, "my-project")
        assert result == "my-project-4"
