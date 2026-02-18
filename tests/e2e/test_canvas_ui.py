"""Canvas UI tests: panel toggling, save behavior, dirty state, persistence."""

from __future__ import annotations

import re

import httpx
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture()
def _conv_with_canvas(api_client: httpx.Client) -> dict:
    """Create a conversation with a canvas, return both ids."""
    resp = api_client.post("/api/conversations", json={"title": "Canvas UI Test"})
    resp.raise_for_status()
    conv = resp.json()
    resp2 = api_client.post(
        f"/api/conversations/{conv['id']}/canvas",
        json={"title": "My Notes", "content": "# Hello"},
    )
    resp2.raise_for_status()
    canvas = resp2.json()
    return {"conversation_id": conv["id"], "canvas": canvas}


def _open_canvas(page: Page) -> None:
    page.locator("#btn-canvas-toggle").click()
    page.wait_for_timeout(500)


def _switch_to_edit(page: Page) -> None:
    page.locator('.canvas-mode-btn[data-mode="edit"]').click()
    page.wait_for_selector("#canvas-cm-wrap .cm-content", state="visible", timeout=10000)


def _load_conversation(page: Page, conv_id: str) -> None:
    page.evaluate(
        """(convId) => {
            if (typeof App !== 'undefined' && App.loadConversation) {
                App.loadConversation(convId);
            }
        }""",
        conv_id,
    )
    page.wait_for_timeout(500)


class TestCanvasToggle:
    def test_toggle_opens_and_closes_canvas(self, authenticated_page: Page, _conv_with_canvas: dict) -> None:
        page = authenticated_page
        _load_conversation(page, _conv_with_canvas["conversation_id"])

        toggle = page.locator("#btn-canvas-toggle")
        panel = page.locator("#canvas-panel")
        chat_main = page.locator(".chat-main")

        # Open
        toggle.click()
        page.wait_for_timeout(500)
        expect(panel).to_be_visible()
        expect(chat_main).to_have_class(re.compile(r"with-canvas"))

        # Close
        page.locator("#canvas-close").click()
        page.wait_for_timeout(300)
        expect(panel).to_be_hidden()

    def test_canvas_title_displays(self, authenticated_page: Page, _conv_with_canvas: dict) -> None:
        page = authenticated_page
        _load_conversation(page, _conv_with_canvas["conversation_id"])

        page.locator("#btn-canvas-toggle").click()
        page.wait_for_timeout(500)

        title_el = page.locator("#canvas-title")
        expect(title_el).to_have_text("My Notes")


class TestCanvasSave:
    def test_save_button_disabled_when_clean(self, authenticated_page: Page, _conv_with_canvas: dict) -> None:
        page = authenticated_page
        _load_conversation(page, _conv_with_canvas["conversation_id"])

        page.locator("#btn-canvas-toggle").click()
        page.wait_for_timeout(500)

        save_btn = page.locator("#canvas-save")
        expect(save_btn).to_be_disabled()

    def test_save_button_enables_on_edit(self, authenticated_page: Page, _conv_with_canvas: dict) -> None:
        page = authenticated_page
        _load_conversation(page, _conv_with_canvas["conversation_id"])

        _open_canvas(page)

        # Switch to edit mode, then type in CodeMirror to trigger dirty state
        _switch_to_edit(page)
        page.locator("#canvas-cm-wrap .cm-content").click()
        page.keyboard.type("new content here")
        page.wait_for_timeout(200)

        save_btn = page.locator("#canvas-save")
        expect(save_btn).to_be_enabled()

    def test_save_persists_content(
        self, authenticated_page: Page, _conv_with_canvas: dict, api_client: httpx.Client
    ) -> None:
        page = authenticated_page
        conv_id = _conv_with_canvas["conversation_id"]
        _load_conversation(page, conv_id)

        _open_canvas(page)

        # Switch to edit mode, select all and replace content
        _switch_to_edit(page)
        page.locator("#canvas-cm-wrap .cm-content").click()
        page.keyboard.press("Meta+a")
        page.keyboard.type("# Persisted Content\n\nThis should survive a reload.")
        page.wait_for_timeout(200)

        # Save
        page.locator("#canvas-save").click()
        page.wait_for_timeout(1000)

        # Verify via API
        resp = api_client.get(f"/api/conversations/{conv_id}/canvas")
        resp.raise_for_status()
        assert "Persisted Content" in resp.json()["content"]


class TestCanvasDirtyState:
    def test_close_with_dirty_shows_confirm(self, authenticated_page: Page, _conv_with_canvas: dict) -> None:
        page = authenticated_page
        _load_conversation(page, _conv_with_canvas["conversation_id"])

        _open_canvas(page)

        # Switch to edit mode, type in CodeMirror to make it dirty
        _switch_to_edit(page)
        page.locator("#canvas-cm-wrap .cm-content").click()
        page.keyboard.type("dirty content")
        page.wait_for_timeout(200)

        # Intercept the confirm dialog
        dialog_fired = []
        page.on("dialog", lambda d: (dialog_fired.append(d.message), d.accept()))

        page.locator("#canvas-close").click()
        page.wait_for_timeout(500)

        assert len(dialog_fired) > 0
        assert "unsaved" in dialog_fired[0].lower()


class TestCanvasCrossConversation:
    def test_canvas_persists_across_conversation_switch(
        self, authenticated_page: Page, api_client: httpx.Client
    ) -> None:
        page = authenticated_page

        # Create conversation 1 with canvas
        resp1 = api_client.post("/api/conversations", json={"title": "Conv With Canvas"})
        resp1.raise_for_status()
        conv1_id = resp1.json()["id"]
        api_client.post(
            f"/api/conversations/{conv1_id}/canvas",
            json={"title": "Canvas 1", "content": "# First"},
        )

        # Create conversation 2 without canvas
        resp2 = api_client.post("/api/conversations", json={"title": "Conv Without Canvas"})
        resp2.raise_for_status()
        conv2_id = resp2.json()["id"]

        # Load conv1 — canvas should appear when toggled
        _load_conversation(page, conv1_id)
        page.locator("#btn-canvas-toggle").click()
        page.wait_for_timeout(500)
        expect(page.locator("#canvas-panel")).to_be_visible()
        expect(page.locator("#canvas-title")).to_have_text("Canvas 1")

        # Close canvas, switch to conv2
        page.locator("#canvas-close").click()
        page.wait_for_timeout(300)
        _load_conversation(page, conv2_id)
        page.wait_for_timeout(500)

        # Canvas panel should be hidden for conv2
        expect(page.locator("#canvas-panel")).to_be_hidden()
