"""Canvas CRUD tests via httpx against the running server."""

from __future__ import annotations

import httpx


class TestCanvasCreate:
    def test_create_canvas_via_api(self, api_client: httpx.Client, conversation_id: str) -> None:
        resp = api_client.post(
            f"/api/conversations/{conversation_id}/canvas",
            json={"title": "API Canvas", "content": "# Test", "language": "markdown"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Canvas"
        assert data["content"] == "# Test"
        assert data["language"] == "markdown"
        assert data["version"] == 1
        assert "id" in data

        # GET it back
        resp2 = api_client.get(f"/api/conversations/{conversation_id}/canvas")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == data["id"]
        assert resp2.json()["content"] == "# Test"

    def test_duplicate_canvas_returns_409(self, api_client: httpx.Client, conversation_id: str) -> None:
        resp = api_client.post(
            f"/api/conversations/{conversation_id}/canvas",
            json={"title": "First", "content": "one"},
        )
        assert resp.status_code == 201

        resp2 = api_client.post(
            f"/api/conversations/{conversation_id}/canvas",
            json={"title": "Second", "content": "two"},
        )
        assert resp2.status_code == 409


class TestCanvasUpdate:
    def test_update_canvas_via_api(self, api_client: httpx.Client, conversation_id: str) -> None:
        api_client.post(
            f"/api/conversations/{conversation_id}/canvas",
            json={"title": "Original", "content": "before"},
        )

        resp = api_client.patch(
            f"/api/conversations/{conversation_id}/canvas",
            json={"content": "after", "title": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "after"
        assert data["title"] == "Updated"
        assert data["version"] == 2

    def test_canvas_version_increments(self, api_client: httpx.Client, conversation_id: str) -> None:
        api_client.post(
            f"/api/conversations/{conversation_id}/canvas",
            json={"title": "Versioned", "content": "v1"},
        )

        api_client.patch(
            f"/api/conversations/{conversation_id}/canvas",
            json={"content": "v2"},
        )
        resp = api_client.patch(
            f"/api/conversations/{conversation_id}/canvas",
            json={"content": "v3"},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 3


class TestCanvasDelete:
    def test_delete_canvas_via_api(self, api_client: httpx.Client, conversation_id: str) -> None:
        api_client.post(
            f"/api/conversations/{conversation_id}/canvas",
            json={"title": "To Delete", "content": "bye"},
        )

        resp = api_client.delete(f"/api/conversations/{conversation_id}/canvas")
        assert resp.status_code == 204

        resp2 = api_client.get(f"/api/conversations/{conversation_id}/canvas")
        assert resp2.status_code == 404

    def test_delete_nonexistent_canvas_returns_404(self, api_client: httpx.Client, conversation_id: str) -> None:
        resp = api_client.delete(f"/api/conversations/{conversation_id}/canvas")
        assert resp.status_code == 404
