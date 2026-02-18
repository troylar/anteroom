"""E2E smoke tests for critical UI flows.

Tests the real server with no mocking of middleware or routing.
Catches regressions like the v1.3.0 Content-Type/CSP issue (#92).

Acceptance criteria from #93:
- Boot server, load page, verify no console errors (CSP violations)
- Click "New Chat", verify conversation is created
- Send a message, verify SSE stream starts
- Create a conversation with a project selected
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import parse_sse_events

pytestmark = [pytest.mark.e2e]


# ---------------------------------------------------------------------------
# API-level smoke tests (httpx — no browser needed)
# ---------------------------------------------------------------------------


class TestServerBootstrap:
    """Verify the server starts and serves the index page correctly.

    These tests use raw httpx (no auth) to verify the unauthenticated
    index route works correctly — this is intentional since GET / must
    be accessible without a session to bootstrap cookies.
    """

    def test_index_returns_200_with_cookies(self, base_url: str) -> None:
        """GET / should return 200 and set both session and CSRF cookies."""
        import httpx

        resp = httpx.get(f"{base_url}/", follow_redirects=True)
        assert resp.status_code == 200

        cookie_names = {c.name for c in resp.cookies.jar}
        assert "anteroom_session" in cookie_names
        assert "anteroom_csrf" in cookie_names

    def test_index_returns_valid_html(self, base_url: str) -> None:
        """GET / should return HTML with essential UI elements."""
        import httpx

        resp = httpx.get(f"{base_url}/", follow_redirects=True)
        assert "text/html" in resp.headers.get("content-type", "")
        assert "btn-send" in resp.text
        assert "message-input" in resp.text
        assert "btn-new-chat" in resp.text

    def test_security_headers_present(self, base_url: str) -> None:
        """Index response should include security headers."""
        import httpx

        resp = httpx.get(f"{base_url}/", follow_redirects=True)
        assert "content-security-policy" in resp.headers
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert "x-frame-options" in resp.headers


class TestAuthEnforcement:
    """Verify auth and CSRF middleware work end-to-end."""

    def test_unauthenticated_api_returns_401(self, base_url: str) -> None:
        """API requests without a valid session cookie should get 401."""
        import httpx

        resp = httpx.get(f"{base_url}/api/conversations")
        assert resp.status_code == 401

    def test_stale_cookie_returns_401(self, base_url: str) -> None:
        """API requests with a stale/invalid session cookie should get 401."""
        import httpx

        resp = httpx.get(
            f"{base_url}/api/conversations",
            cookies={"anteroom_session": "invalid-stale-token"},
        )
        assert resp.status_code == 401

    def test_missing_csrf_returns_403(self, base_url: str, _session_cookies: dict[str, str]) -> None:
        """State-changing requests without CSRF token should be rejected."""
        import httpx

        session_token = _session_cookies.get("anteroom_session", "")
        resp = httpx.post(
            f"{base_url}/api/conversations",
            cookies={"anteroom_session": session_token},
            json={"title": "No CSRF"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 403


class TestConversationCRUD:
    """Verify conversation creation and listing through the real server."""

    def test_create_conversation(self, api_client) -> None:
        """POST /api/conversations should create a new chat conversation."""
        resp = api_client.post("/api/conversations", json={"title": "Smoke Test Chat"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Smoke Test Chat"
        assert data["type"] == "chat"
        assert "id" in data

    def test_create_conversation_requires_content_type(self, api_client) -> None:
        """POST without Content-Type: application/json should be rejected.

        This catches the v1.3.0 regression (#92) where missing Content-Type
        headers caused 415 errors.
        """
        resp = api_client.post(
            "/api/conversations",
            content=b'{"title": "test"}',
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code in (415, 422)

    def test_list_conversations(self, api_client, conversation_id: str) -> None:
        """GET /api/conversations should return the created conversation."""
        resp = api_client.get("/api/conversations")
        assert resp.status_code == 200
        conversations = resp.json()
        assert any(c["id"] == conversation_id for c in conversations)

    def test_get_conversation_detail(self, api_client, conversation_id: str) -> None:
        """GET /api/conversations/{id} should return conversation with messages."""
        resp = api_client.get(f"/api/conversations/{conversation_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conversation_id
        assert "messages" in data

    def test_get_nonexistent_conversation_returns_404(self, api_client) -> None:
        """GET /api/conversations/{bad-id} should return 404."""
        resp = api_client.get("/api/conversations/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestChatSSEStream:
    """Verify that sending a message produces an SSE stream."""

    def test_send_message_returns_sse_stream(self, api_client, conversation_id: str) -> None:
        """POST /api/conversations/{id}/chat should return an SSE event stream.

        The AI endpoint is unreachable (dummy URL), so we expect an error event,
        but the key assertion is that the server starts an SSE stream at all
        (correct Content-Type, event format).
        """
        with api_client.stream(
            "POST",
            f"/api/conversations/{conversation_id}/chat",
            json={"message": "hello"},
            timeout=15,
        ) as resp:
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert "text/event-stream" in content_type

            body = resp.read().decode()

        events = parse_sse_events(SimpleNamespace(text=body))
        assert len(events) > 0
        event_types = {e["event"] for e in events}
        # Should end with either "done" or "error" (AI unreachable)
        assert event_types & {"done", "error"}

    def test_send_message_stores_user_message(self, api_client, conversation_id: str) -> None:
        """After sending a message, the user message should be persisted."""
        with api_client.stream(
            "POST",
            f"/api/conversations/{conversation_id}/chat",
            json={"message": "test persistence"},
            timeout=15,
        ) as resp:
            resp.read()

        detail = api_client.get(f"/api/conversations/{conversation_id}")
        assert detail.status_code == 200
        messages = detail.json()["messages"]
        user_messages = [m for m in messages if m["role"] == "user"]
        assert any("test persistence" in m["content"] for m in user_messages)


class TestProjectConversation:
    """Verify creating a conversation linked to a project."""

    def test_create_project(self, api_client) -> None:
        """POST /api/projects should create a new project."""
        resp = api_client.post(
            "/api/projects",
            json={"name": "Smoke Test Project", "instructions": "You are a test assistant."},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Smoke Test Project"
        assert "id" in data

    def test_create_conversation_with_project(self, api_client) -> None:
        """A conversation created with a project_id should be linked to that project."""
        project = api_client.post(
            "/api/projects",
            json={"name": "Project Link Test"},
        ).json()

        conv = api_client.post(
            "/api/conversations",
            json={"title": "Project Chat", "project_id": project["id"]},
        )
        assert conv.status_code == 201
        conv_data = conv.json()
        assert conv_data["project_id"] == project["id"]

    def test_list_conversations_by_project(self, api_client) -> None:
        """Conversations should be filterable by project_id."""
        project = api_client.post("/api/projects", json={"name": "Filter Test"}).json()
        api_client.post(
            "/api/conversations",
            json={"title": "In Project", "project_id": project["id"]},
        )
        api_client.post("/api/conversations", json={"title": "No Project"})

        resp = api_client.get(f"/api/conversations?project_id={project['id']}")
        assert resp.status_code == 200
        filtered = resp.json()
        assert any(c["title"] == "In Project" for c in filtered)
        assert not any(c["title"] == "No Project" for c in filtered)


# ---------------------------------------------------------------------------
# Playwright browser smoke tests (skip if Playwright unavailable)
# ---------------------------------------------------------------------------

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

requires_playwright = pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")


@requires_playwright
class TestBrowserPageLoad:
    """Verify the page loads in a real browser without errors."""

    def test_no_console_errors_on_load(self, authenticated_page) -> None:
        """Loading the page should produce no console errors."""
        console_errors: list[str] = []

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        page = authenticated_page
        page.on("console", on_console)

        page.reload()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector("#btn-send", timeout=10000)

        # EventSource to the dummy AI endpoint produces expected connection
        # errors — filter those out but catch everything else (CSP, JS errors)
        csp_violations = [e for e in console_errors if "Content-Security-Policy" in e or "Refused to" in e]
        assert csp_violations == [], f"CSP violations found: {csp_violations}"

        js_errors = [
            e
            for e in console_errors
            if "Content-Security-Policy" not in e
            and "Refused to" not in e
            and "ERR_CONNECTION_REFUSED" not in e  # expected: dummy AI endpoint
            and "/api/events" not in e  # expected: SSE reconnect to test server
        ]
        assert js_errors == [], f"Unexpected JS errors: {js_errors}"

    def test_essential_ui_elements_present(self, authenticated_page) -> None:
        """The page should have the sidebar, input, and send button."""
        page = authenticated_page
        assert page.locator("#sidebar").is_visible()
        assert page.locator("#message-input").is_visible()
        assert page.locator("#btn-send").is_visible()
        assert page.locator("#btn-new-chat").is_visible()


@requires_playwright
class TestBrowserNewChat:
    """Verify the New Chat button creates a conversation in the browser."""

    def test_click_new_chat_creates_conversation(self, authenticated_page, api_client) -> None:
        """Clicking 'New Chat' should create a conversation visible in the sidebar."""
        import time

        page = authenticated_page

        before = api_client.get("/api/conversations").json()
        before_count = len(before)

        page.locator("#btn-new-chat").click()

        # Poll the API for the new conversation (avoids wait_for_function
        # which requires unsafe-eval, blocked by CSP)
        deadline = time.monotonic() + 5
        after = before
        while time.monotonic() < deadline:
            after = api_client.get("/api/conversations").json()
            if len(after) > before_count:
                break
            time.sleep(0.2)

        assert len(after) > before_count

    def test_new_chat_activates_input(self, authenticated_page) -> None:
        """After clicking New Chat, the message input should be enabled."""
        page = authenticated_page
        page.locator("#btn-new-chat").click()
        page.wait_for_timeout(500)

        input_el = page.locator("#message-input")
        assert input_el.is_visible()
        assert input_el.is_enabled()
