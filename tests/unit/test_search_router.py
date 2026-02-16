"""Tests for the search router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anteroom.routers.search import router


def _make_app(*, vec_enabled: bool = False, embedding_service=None) -> FastAPI:
    """Create a minimal FastAPI app with the search router."""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    # Minimal state
    app.state.vec_enabled = vec_enabled
    app.state.embedding_service = embedding_service

    # Mock db
    mock_db = MagicMock()
    mock_db_manager = MagicMock()
    mock_db_manager.get.return_value = mock_db
    app.state.db = mock_db
    app.state.db_manager = mock_db_manager

    return app


class TestUnifiedSearch:
    def test_keyword_mode_uses_fts(self) -> None:
        app = _make_app()
        with patch("anteroom.routers.search.storage") as mock_storage:
            mock_storage.list_conversations.return_value = [{"id": "c1", "title": "Test Conv", "message_count": 5}]
            client = TestClient(app)
            resp = client.get("/api/search?q=hello&mode=keyword")
            assert resp.status_code == 200
            data = resp.json()
            assert data["mode"] == "keyword"
            assert len(data["results"]) == 1

    def test_auto_mode_falls_back_to_keyword(self) -> None:
        app = _make_app(vec_enabled=False)
        with patch("anteroom.routers.search.storage") as mock_storage:
            mock_storage.list_conversations.return_value = []
            client = TestClient(app)
            resp = client.get("/api/search?q=test&mode=auto")
            assert resp.status_code == 200
            assert resp.json()["mode"] == "keyword"

    def test_semantic_mode_errors_when_unavailable(self) -> None:
        app = _make_app(vec_enabled=False)
        client = TestClient(app)
        resp = client.get("/api/search?q=test&mode=semantic")
        assert resp.status_code == 503

    def test_auto_mode_uses_semantic_when_available(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=[0.1] * 1536)
        app = _make_app(vec_enabled=True, embedding_service=service)

        with patch("anteroom.routers.search.storage") as mock_storage:
            mock_storage.search_similar_messages.return_value = [
                {
                    "message_id": "m1",
                    "conversation_id": "c1",
                    "content": "Hello",
                    "role": "user",
                    "distance": 0.1,
                }
            ]
            client = TestClient(app)
            resp = client.get("/api/search?q=hello&mode=auto")
            assert resp.status_code == 200
            data = resp.json()
            assert data["mode"] == "semantic"

    def test_missing_query_returns_422(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/search")
        assert resp.status_code == 422

    def test_invalid_mode_returns_422(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/search?q=test&mode=invalid")
        assert resp.status_code == 422


class TestSemanticSearch:
    def test_returns_grouped_results(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=[0.1] * 1536)
        app = _make_app(vec_enabled=True, embedding_service=service)

        with patch("anteroom.routers.search.storage") as mock_storage:
            mock_storage.search_similar_messages.return_value = [
                {"message_id": "m1", "conversation_id": "c1", "content": "Hello", "role": "user", "distance": 0.1},
                {"message_id": "m2", "conversation_id": "c1", "content": "World", "role": "assistant", "distance": 0.2},
            ]
            mock_storage.get_conversation.return_value = {"title": "Test Conv"}

            client = TestClient(app)
            resp = client.get("/api/search/semantic?q=hello")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["results"]) == 1  # grouped by conversation
            assert data["results"][0]["conversation_id"] == "c1"
            assert len(data["results"][0]["messages"]) == 2

    def test_errors_when_service_unavailable(self) -> None:
        app = _make_app(vec_enabled=True, embedding_service=None)
        client = TestClient(app)
        resp = client.get("/api/search/semantic?q=hello")
        assert resp.status_code == 503

    def test_errors_when_vec_not_loaded(self) -> None:
        service = AsyncMock()
        app = _make_app(vec_enabled=False, embedding_service=service)
        client = TestClient(app)
        resp = client.get("/api/search/semantic?q=hello")
        assert resp.status_code == 503

    def test_errors_when_embedding_fails(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=None)
        app = _make_app(vec_enabled=True, embedding_service=service)

        client = TestClient(app)
        resp = client.get("/api/search/semantic?q=hello")
        assert resp.status_code == 500


class TestAutoModeFallback:
    def test_auto_falls_back_to_keyword_when_embed_returns_none(self) -> None:
        service = AsyncMock()
        service.embed = AsyncMock(return_value=None)
        app = _make_app(vec_enabled=True, embedding_service=service)

        with patch("anteroom.routers.search.storage") as mock_storage:
            mock_storage.list_conversations.return_value = []
            client = TestClient(app)
            resp = client.get("/api/search?q=test&mode=auto")
            assert resp.status_code == 200
            assert resp.json()["mode"] == "keyword"
