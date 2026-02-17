"""Unit tests for canvas CRUD endpoints in the conversations router."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anteroom.routers.conversations import router

_CANVAS = {
    "id": str(uuid.uuid4()),
    "conversation_id": str(uuid.uuid4()),
    "title": "Test Canvas",
    "content": "# Hello",
    "language": None,
    "version": 1,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
    "user_id": None,
    "user_display_name": None,
}

_CONV = {
    "id": _CANVAS["conversation_id"],
    "title": "Test",
    "type": "chat",
    "created_at": "2024-01-01",
    "updated_at": "2024-01-01",
}


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    mock_db = MagicMock()
    mock_db_manager = MagicMock()
    mock_db_manager.get.return_value = mock_db
    app.state.db = mock_db
    app.state.db_manager = mock_db_manager
    mock_config = MagicMock()
    mock_config.identity = None
    mock_config.app.data_dir = MagicMock()
    app.state.config = mock_config
    return app


class TestCreateCanvasEndpoint:
    def test_create_canvas_success(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = None
            mock_storage.create_canvas.return_value = _CANVAS
            client = TestClient(app)
            resp = client.post(
                f"/api/conversations/{conv_id}/canvas",
                json={"title": "Test Canvas", "content": "# Hello"},
            )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Test Canvas"

    def test_create_canvas_409_duplicate(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = _CANVAS
            client = TestClient(app)
            resp = client.post(
                f"/api/conversations/{conv_id}/canvas",
                json={"title": "Dup", "content": "C"},
            )
        assert resp.status_code == 409

    def test_create_canvas_404_no_conversation(self) -> None:
        app = _make_app()
        fake_id = str(uuid.uuid4())
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = None
            client = TestClient(app)
            resp = client.post(
                f"/api/conversations/{fake_id}/canvas",
                json={"title": "T", "content": "C"},
            )
        assert resp.status_code == 404

    def test_create_canvas_invalid_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.post(
            "/api/conversations/not-a-uuid/canvas",
            json={"title": "T", "content": "C"},
        )
        assert resp.status_code == 400

    def test_create_canvas_title_too_long(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        client = TestClient(app)
        resp = client.post(
            f"/api/conversations/{conv_id}/canvas",
            json={"title": "x" * 201, "content": "C"},
        )
        assert resp.status_code == 422


class TestGetCanvasEndpoint:
    def test_get_canvas_success(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = _CANVAS
            client = TestClient(app)
            resp = client.get(f"/api/conversations/{conv_id}/canvas")
        assert resp.status_code == 200
        assert resp.json()["content"] == "# Hello"

    def test_get_canvas_404_no_canvas(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = None
            client = TestClient(app)
            resp = client.get(f"/api/conversations/{conv_id}/canvas")
        assert resp.status_code == 404

    def test_get_canvas_404_no_conversation(self) -> None:
        app = _make_app()
        fake_id = str(uuid.uuid4())
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = None
            client = TestClient(app)
            resp = client.get(f"/api/conversations/{fake_id}/canvas")
        assert resp.status_code == 404

    def test_get_canvas_invalid_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/conversations/not-a-uuid/canvas")
        assert resp.status_code == 400


class TestUpdateCanvasEndpoint:
    def test_update_canvas_success(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        updated = {**_CANVAS, "content": "updated", "version": 2}
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = _CANVAS
            mock_storage.update_canvas.return_value = updated
            client = TestClient(app)
            resp = client.patch(
                f"/api/conversations/{conv_id}/canvas",
                json={"content": "updated"},
            )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    def test_update_canvas_404_no_canvas(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = None
            client = TestClient(app)
            resp = client.patch(
                f"/api/conversations/{conv_id}/canvas",
                json={"content": "data"},
            )
        assert resp.status_code == 404

    def test_update_canvas_404_no_conversation(self) -> None:
        app = _make_app()
        fake_id = str(uuid.uuid4())
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = None
            client = TestClient(app)
            resp = client.patch(
                f"/api/conversations/{fake_id}/canvas",
                json={"content": "data"},
            )
        assert resp.status_code == 404

    def test_update_canvas_invalid_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.patch(
            "/api/conversations/not-a-uuid/canvas",
            json={"content": "data"},
        )
        assert resp.status_code == 400

    def test_update_canvas_title_only(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        updated = {**_CANVAS, "title": "New Title Only", "version": 2}
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = _CANVAS
            mock_storage.update_canvas.return_value = updated
            client = TestClient(app)
            resp = client.patch(
                f"/api/conversations/{conv_id}/canvas",
                json={"title": "New Title Only"},
            )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title Only"
        assert resp.json()["content"] == _CANVAS["content"]

    def test_update_canvas_returns_none(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = _CANVAS
            mock_storage.update_canvas.return_value = None
            client = TestClient(app)
            resp = client.patch(
                f"/api/conversations/{conv_id}/canvas",
                json={"content": "data"},
            )
        assert resp.status_code == 404


class TestDeleteCanvasEndpoint:
    def test_delete_canvas_success(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = _CANVAS
            mock_storage.delete_canvas.return_value = True
            client = TestClient(app)
            resp = client.delete(f"/api/conversations/{conv_id}/canvas")
        assert resp.status_code == 204

    def test_delete_canvas_404_no_canvas(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = _CONV
            mock_storage.get_canvas_for_conversation.return_value = None
            client = TestClient(app)
            resp = client.delete(f"/api/conversations/{conv_id}/canvas")
        assert resp.status_code == 404

    def test_delete_canvas_404_no_conversation(self) -> None:
        app = _make_app()
        fake_id = str(uuid.uuid4())
        with patch("anteroom.routers.conversations.storage") as mock_storage:
            mock_storage.get_conversation.return_value = None
            client = TestClient(app)
            resp = client.delete(f"/api/conversations/{fake_id}/canvas")
        assert resp.status_code == 404

    def test_delete_canvas_invalid_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/conversations/not-a-uuid/canvas")
        assert resp.status_code == 400


class TestCanvasContentTypeEnforcement:
    """Canvas endpoints — Content-Type enforcement."""

    def test_create_canvas_rejects_non_json(self) -> None:
        """Non-JSON body rejected: Pydantic fires 422 before _require_json can return 415."""
        app = _make_app()
        conv_id = _CONV["id"]
        client = TestClient(app)
        resp = client.post(
            f"/api/conversations/{conv_id}/canvas",
            content="title=Test",
            headers={"content-type": "text/plain"},
        )
        assert resp.status_code == 422

    def test_update_canvas_rejects_non_json(self) -> None:
        """Non-JSON body rejected: Pydantic fires 422 before _require_json can return 415."""
        app = _make_app()
        conv_id = _CONV["id"]
        client = TestClient(app)
        resp = client.patch(
            f"/api/conversations/{conv_id}/canvas",
            content="content=data",
            headers={"content-type": "text/plain"},
        )
        assert resp.status_code == 422

    def test_create_canvas_rejects_empty_title(self) -> None:
        app = _make_app()
        conv_id = _CONV["id"]
        client = TestClient(app)
        resp = client.post(
            f"/api/conversations/{conv_id}/canvas",
            json={"title": "", "content": "C"},
        )
        assert resp.status_code == 422
