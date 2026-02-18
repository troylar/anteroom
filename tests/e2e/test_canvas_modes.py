"""Canvas mode switching tests: Edit/Preview transitions and content round-trips."""

from __future__ import annotations

import re

import httpx
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture()
def _canvas_page(authenticated_page: Page, api_client: httpx.Client) -> tuple[Page, str]:
    """Create a conversation with markdown-rich canvas content, open it, return (page, conv_id)."""
    resp = api_client.post("/api/conversations", json={"title": "Mode Test"})
    resp.raise_for_status()
    conv_id = resp.json()["id"]

    api_client.post(
        f"/api/conversations/{conv_id}/canvas",
        json={
            "title": "Mode Canvas",
            "content": "# Heading\n\n**bold text**\n\n- item one\n- item two",
        },
    )

    page = authenticated_page
    page.evaluate(
        "(convId) => { if (typeof App !== 'undefined' && App.loadConversation) App.loadConversation(convId); }",
        conv_id,
    )
    page.wait_for_timeout(500)

    page.locator("#btn-canvas-toggle").click()
    page.wait_for_timeout(500)

    return page, conv_id


class TestDefaultMode:
    def test_default_mode_is_preview(self, _canvas_page: tuple[Page, str]) -> None:
        page, _ = _canvas_page
        cm_wrap = page.locator("#canvas-cm-wrap")
        preview = page.locator("#canvas-preview")

        expect(preview).to_be_visible()
        expect(cm_wrap).to_be_hidden()

        preview_btn = page.locator('.canvas-mode-btn[data-mode="preview"]')
        expect(preview_btn).to_have_class(re.compile(r"active"))


class TestModeSwitching:
    def test_switch_to_edit(self, _canvas_page: tuple[Page, str]) -> None:
        page, _ = _canvas_page
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_timeout(300)

        expect(page.locator("#canvas-cm-wrap")).to_be_visible()
        expect(page.locator("#canvas-preview")).to_be_hidden()

        cm_content = page.evaluate("document.querySelector('#canvas-cm-wrap .cm-content').textContent")
        assert "Heading" in cm_content

    def test_preview_to_edit_to_preview_preserves_content(self, _canvas_page: tuple[Page, str]) -> None:
        page, _ = _canvas_page

        # Default is preview — verify content rendered
        preview = page.locator("#canvas-preview")
        expect(preview).to_contain_text("Heading")
        expect(preview).to_contain_text("bold text")

        # Switch to Edit
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_timeout(300)
        cm_content = page.evaluate("document.querySelector('#canvas-cm-wrap .cm-content').textContent")
        assert "Heading" in cm_content
        assert "bold text" in cm_content

        # Switch back to Preview
        page.locator('.canvas-mode-btn[data-mode="preview"]').click()
        page.wait_for_timeout(300)
        expect(preview).to_contain_text("Heading")
        expect(preview).to_contain_text("bold text")


class TestFullRoundTrip:
    def test_preview_edit_preview_round_trip(self, _canvas_page: tuple[Page, str]) -> None:
        page, _ = _canvas_page

        # Default is preview — content rendered
        preview = page.locator("#canvas-preview")
        expect(preview).to_be_visible()
        preview_text = preview.inner_text()
        assert "Heading" in preview_text

        # Preview → Edit
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_timeout(300)
        cm_text = page.evaluate("document.querySelector('#canvas-cm-wrap .cm-content').textContent")
        assert "Heading" in cm_text

        # Edit → Preview
        page.locator('.canvas-mode-btn[data-mode="preview"]').click()
        page.wait_for_timeout(300)
        preview_text2 = preview.inner_text()
        assert "Heading" in preview_text2


_COMPLEX_MARKDOWN = """\
# Project README

## Features

Here is **bold**, *italic*, and ~~strikethrough~~ text.

### Code Block

```python
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
```

### Table

| Name   | Role      | Status |
| ------ | --------- | ------ |
| Alice  | Engineer  | Active |
| Bob    | Designer  | Away   |

### Lists

1. First ordered item
2. Second ordered item
   - Nested bullet
   - Another nested bullet
3. Third ordered item

- [x] Completed task
- [ ] Pending task

### Blockquote

> This is a blockquote.
> It spans multiple lines.

### Links and Inline Code

Use `pip install anteroom` to install. See [docs](https://example.com).
"""


@pytest.fixture()
def _complex_canvas_page(authenticated_page: Page, api_client: httpx.Client) -> tuple[Page, str]:
    """Create a canvas with complex markdown, open it, return (page, conv_id)."""
    resp = api_client.post("/api/conversations", json={"title": "Complex MD Test"})
    resp.raise_for_status()
    conv_id = resp.json()["id"]

    api_client.post(
        f"/api/conversations/{conv_id}/canvas",
        json={"title": "Complex Markdown", "content": _COMPLEX_MARKDOWN},
    )

    page = authenticated_page
    page.evaluate(
        "(convId) => { if (typeof App !== 'undefined' && App.loadConversation) App.loadConversation(convId); }",
        conv_id,
    )
    page.wait_for_timeout(500)

    page.locator("#btn-canvas-toggle").click()
    page.wait_for_timeout(500)

    # Ensure CodeMirror bundle is loaded and editor is initialized
    page.wait_for_timeout(300)

    return page, conv_id


class TestComplexMarkdown:
    """Test complex markdown is stored losslessly in CodeMirror's Edit mode."""

    def test_complex_md_stored_losslessly(self, _complex_canvas_page: tuple[Page, str]) -> None:
        page, _ = _complex_canvas_page

        # Switch to edit mode to init CodeMirror
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_selector("#canvas-cm-wrap .cm-content", state="visible", timeout=10000)

        # CodeMirror stores markdown as-is — no conversion loss
        md = page.evaluate("Canvas.getMarkdown()")

        assert "Project README" in md
        assert "fibonacci" in md
        assert "```python" in md
        assert "| Alice" in md
        assert "> This is a blockquote." in md
        assert "`pip install anteroom`" in md

    def test_complex_md_preview_renders_html(self, _complex_canvas_page: tuple[Page, str]) -> None:
        page, _ = _complex_canvas_page

        page.locator('.canvas-mode-btn[data-mode="preview"]').click()
        page.wait_for_timeout(300)

        preview = page.locator("#canvas-preview")
        expect(preview).to_be_visible()

        expect(preview.locator("h1")).to_contain_text("Project README")
        expect(preview.locator("h2").first).to_contain_text("Features")
        expect(preview.locator("code").first).to_be_visible()
        expect(preview.locator("table").first).to_be_visible()
        expect(preview.locator("blockquote")).to_be_visible()

    def test_complex_md_edit_survives_round_trip(self, _complex_canvas_page: tuple[Page, str]) -> None:
        page, _ = _complex_canvas_page

        # Switch to Edit mode to type
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_timeout(300)

        page.locator("#canvas-cm-wrap .cm-content").click()
        page.keyboard.press("Meta+End")
        page.keyboard.type("\n\n## New Section\n\nAdded in edit mode.\n")
        page.wait_for_timeout(100)

        # Edit → Preview
        page.locator('.canvas-mode-btn[data-mode="preview"]').click()
        page.wait_for_timeout(300)

        preview = page.locator("#canvas-preview")
        expect(preview).to_contain_text("New Section")
        expect(preview).to_contain_text("Added in edit mode")

        # Preview → Edit
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_timeout(300)

        cm_text = page.evaluate("document.querySelector('#canvas-cm-wrap .cm-content').textContent")
        assert "New Section" in cm_text
        assert "Project README" in cm_text

    def test_complex_md_full_cycle(self, _complex_canvas_page: tuple[Page, str]) -> None:
        """Preview → Edit → Preview. Content persists through all transitions."""
        page, _ = _complex_canvas_page

        # Default is preview
        preview = page.locator("#canvas-preview")
        expect(preview).to_contain_text("Project README")

        # Preview → Edit
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_timeout(300)
        cm_text = page.evaluate("document.querySelector('#canvas-cm-wrap .cm-content').textContent")
        assert "fibonacci" in cm_text

        # Edit → Preview
        page.locator('.canvas-mode-btn[data-mode="preview"]').click()
        page.wait_for_timeout(300)
        expect(preview).to_contain_text("Project README")


class TestComplexMarkdownSSE:
    """Test that AI-simulated updates with complex markdown render correctly."""

    def test_ai_update_complex_md_in_edit_mode(self, _complex_canvas_page: tuple[Page, str]) -> None:
        page, _ = _complex_canvas_page

        # Switch to edit mode to init CodeMirror
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_selector("#canvas-cm-wrap .cm-content", state="visible", timeout=10000)

        ai_content = (
            "# AI Update\\n\\n## Code\\n\\n```js\\nconst x = 42;\\n```\\n\\n"
            "| Col | Val |\\n| --- | --- |\\n| A   | 1   |\\n\\n> Important note\\n"
        )
        page.evaluate(
            f"""() => {{
                Canvas.handleCanvasUpdated({{
                    content: '{ai_content}',
                    title: 'AI Complex Update'
                }});
            }}"""
        )
        page.wait_for_timeout(500)

        expect(page.locator("#canvas-title")).to_have_text("AI Complex Update")

        # Read directly from CodeMirror state
        cm_text = page.evaluate("Canvas.getMarkdown()")
        assert "AI Update" in cm_text
        assert "const x = 42" in cm_text

    def test_ai_update_complex_md_while_in_edit(self, _complex_canvas_page: tuple[Page, str]) -> None:
        page, _ = _complex_canvas_page

        # Switch to edit mode to init CodeMirror
        page.locator('.canvas-mode-btn[data-mode="edit"]').click()
        page.wait_for_selector("#canvas-cm-wrap .cm-content", state="visible", timeout=10000)

        # AI sends update while in edit mode
        page.evaluate(
            """() => {
                Canvas.handleCanvasUpdated({
                    content: '# Raw Update\\n\\n**bold** and *italic*\\n\\n- list item 1\\n- list item 2\\n'
                });
            }"""
        )
        page.wait_for_timeout(300)

        cm_text = page.evaluate("Canvas.getMarkdown()")
        assert "Raw Update" in cm_text
