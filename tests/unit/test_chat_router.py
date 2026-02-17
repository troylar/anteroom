"""Tests for chat router endpoints (stop_generation, get_attachment)."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anteroom.routers.chat import router


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
    mock_config.app.data_dir = Path(tempfile.mkdtemp())
    mock_config.app.tls = False
    app.state.config = mock_config

    app.state.tool_registry = MagicMock()
    app.state.mcp_manager = MagicMock()

    return app


class TestStopGenerationEndpoint:
    """POST /conversations/{id}/stop — cancel active generation."""

    def test_stop_success(self) -> None:
        conv_id = str(uuid.uuid4())
        app = _make_app()
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_conversation.return_value = {"id": conv_id, "type": "chat"}
            client = TestClient(app)
            resp = client.post(f"/api/conversations/{conv_id}/stop")
            assert resp.status_code == 200
            assert resp.json()["status"] == "stopped"

    def test_stop_conversation_not_found(self) -> None:
        conv_id = str(uuid.uuid4())
        app = _make_app()
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_conversation.return_value = None
            client = TestClient(app)
            resp = client.post(f"/api/conversations/{conv_id}/stop")
            assert resp.status_code == 404

    def test_stop_invalid_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.post("/api/conversations/bad-uuid/stop")
        assert resp.status_code == 400

    def test_stop_no_active_stream(self) -> None:
        """Stop should succeed even when no stream is active (idempotent)."""
        conv_id = str(uuid.uuid4())
        app = _make_app()
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_conversation.return_value = {"id": conv_id, "type": "chat"}
            client = TestClient(app)
            resp = client.post(f"/api/conversations/{conv_id}/stop")
            assert resp.status_code == 200


class TestGetAttachmentEndpoint:
    """GET /attachments/{id} — retrieve attachment files."""

    def test_attachment_not_found(self) -> None:
        att_id = str(uuid.uuid4())
        app = _make_app()
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_attachment.return_value = None
            client = TestClient(app)
            resp = client.get(f"/api/attachments/{att_id}")
            assert resp.status_code == 404

    def test_attachment_invalid_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/attachments/bad-uuid")
        assert resp.status_code == 400

    def test_attachment_path_traversal_blocked(self) -> None:
        att_id = str(uuid.uuid4())
        app = _make_app()
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_attachment.return_value = {
                "id": att_id,
                "storage_path": "../../etc/passwd",
                "mime_type": "text/plain",
                "filename": "passwd",
            }
            client = TestClient(app)
            resp = client.get(f"/api/attachments/{att_id}")
            assert resp.status_code == 403

    def test_attachment_file_missing(self) -> None:
        att_id = str(uuid.uuid4())
        app = _make_app()
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_attachment.return_value = {
                "id": att_id,
                "storage_path": "attachments/nonexistent.txt",
                "mime_type": "text/plain",
                "filename": "nonexistent.txt",
            }
            client = TestClient(app)
            resp = client.get(f"/api/attachments/{att_id}")
            assert resp.status_code == 404

    def test_attachment_inline_for_image(self) -> None:
        att_id = str(uuid.uuid4())
        app = _make_app()
        data_dir = app.state.config.app.data_dir
        # Create a real file in data_dir
        att_dir = data_dir / "attachments"
        att_dir.mkdir(parents=True, exist_ok=True)
        test_file = att_dir / "test.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_attachment.return_value = {
                "id": att_id,
                "storage_path": "attachments/test.png",
                "mime_type": "image/png",
                "filename": "test.png",
            }
            client = TestClient(app)
            resp = client.get(f"/api/attachments/{att_id}")
            assert resp.status_code == 200
            assert "inline" in resp.headers.get("content-disposition", "")

    def test_attachment_download_for_non_image(self) -> None:
        att_id = str(uuid.uuid4())
        app = _make_app()
        data_dir = app.state.config.app.data_dir
        att_dir = data_dir / "attachments"
        att_dir.mkdir(parents=True, exist_ok=True)
        test_file = att_dir / "doc.pdf"
        test_file.write_bytes(b"%PDF-1.4 test content")
        with patch("anteroom.routers.chat.storage") as mock_storage:
            mock_storage.get_attachment.return_value = {
                "id": att_id,
                "storage_path": "attachments/doc.pdf",
                "mime_type": "application/pdf",
                "filename": "doc.pdf",
            }
            client = TestClient(app)
            resp = client.get(f"/api/attachments/{att_id}")
            assert resp.status_code == 200
            assert "attachment" in resp.headers.get("content-disposition", "")
