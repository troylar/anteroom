"""Canvas SSE event tests: simulate AI-driven canvas events via page.evaluate."""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture()
def _open_canvas_page(authenticated_page: Page, api_client: httpx.Client) -> tuple[Page, str]:
    """Create a conversation with canvas, load it, open the canvas panel."""
    resp = api_client.post("/api/conversations", json={"title": "SSE Test"})
    resp.raise_for_status()
    conv_id = resp.json()["id"]

    api_client.post(
        f"/api/conversations/{conv_id}/canvas",
        json={"title": "SSE Canvas", "content": "# Original"},
    )

    page = authenticated_page
    page.evaluate(
        "(convId) => { if (typeof App !== 'undefined' && App.loadConversation) App.loadConversation(convId); }",
        conv_id,
    )
    page.wait_for_timeout(500)

    page.locator("#btn-canvas-toggle").click()
    page.wait_for_selector("#canvas-panel", state="visible", timeout=5000)
    page.wait_for_timeout(500)

    return page, conv_id


class TestCanvasCreatedEvent:
    def test_canvas_created_event_opens_panel(self, authenticated_page: Page, api_client: httpx.Client) -> None:
        """Calling Canvas.handleCanvasCreated() should open the panel with content."""
        page = authenticated_page

        # Create a conversation without a canvas
        resp = api_client.post("/api/conversations", json={"title": "SSE Create"})
        resp.raise_for_status()
        conv_id = resp.json()["id"]

        page.evaluate(
            "(convId) => { if (typeof App !== 'undefined' && App.loadConversation) App.loadConversation(convId); }",
            conv_id,
        )
        page.wait_for_timeout(500)

        # Panel should be hidden initially
        expect(page.locator("#canvas-panel")).to_be_hidden()

        # Simulate the SSE event
        page.evaluate(
            """() => {
                Canvas.handleCanvasCreated({
                    id: 'fake-id-123',
                    title: 'AI Created',
                    content: '# Hello from AI'
                });
            }"""
        )
        page.wait_for_timeout(500)

        expect(page.locator("#canvas-panel")).to_be_visible()
        expect(page.locator("#canvas-title")).to_have_text("AI Created")


class TestCanvasUpdatedEvent:
    def test_canvas_updated_event_updates_content(self, _open_canvas_page: tuple[Page, str]) -> None:
        page, _ = _open_canvas_page

        # Fire update event
        page.evaluate(
            """() => {
                Canvas.handleCanvasUpdated({
                    content: '# Updated by AI',
                    title: 'Updated Title'
                });
            }"""
        )
        page.wait_for_timeout(500)

        expect(page.locator("#canvas-title")).to_have_text("Updated Title")

        # In preview mode, verify rendered preview contains updated content
        expect(page.locator("#canvas-preview")).to_contain_text("Updated by AI")

        # Switch to edit mode and verify CodeMirror has the updated content
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_selector("#canvas-cm-wrap .cm-content", state="visible", timeout=10000)
        cm_text = page.evaluate("Canvas.getMarkdown()")
        assert "Updated by AI" in cm_text

    def test_canvas_updated_applies_over_dirty(self, _open_canvas_page: tuple[Page, str]) -> None:
        page, _ = _open_canvas_page

        # Switch to edit mode to interact with CodeMirror
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_selector("#canvas-cm-wrap .cm-content", state="visible", timeout=10000)

        # Make a user edit in CodeMirror (dirty state)
        page.locator("#canvas-cm-wrap .cm-content").click()
        page.keyboard.type("User's draft content")
        page.wait_for_timeout(200)

        # Save should be enabled (dirty)
        expect(page.locator("#canvas-save")).to_be_enabled()

        # AI update arrives — should overwrite user's draft
        page.evaluate(
            """() => {
                Canvas.handleCanvasUpdated({
                    content: '# AI wins'
                });
            }"""
        )
        page.wait_for_timeout(500)

        cm_text = page.evaluate("Canvas.getMarkdown()")
        assert "AI wins" in cm_text

        # Dirty state should be cleared after AI update
        expect(page.locator("#canvas-save")).to_be_disabled()
