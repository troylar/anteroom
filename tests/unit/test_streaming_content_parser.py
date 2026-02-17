"""Tests for _extract_streaming_content in chat router."""

from __future__ import annotations

from anteroom.routers.chat import _extract_streaming_content


class TestExtractStreamingContent:
    """_extract_streaming_content — incremental JSON content parser."""

    def test_returns_none_before_content_key(self) -> None:
        assert _extract_streaming_content('{"title": "Hello"') is None
        assert _extract_streaming_content("") is None
        assert _extract_streaming_content("{") is None

    def test_returns_empty_string_after_content_key_opens(self) -> None:
        result = _extract_streaming_content('{"content": "')
        assert result == ""

    def test_returns_partial_content(self) -> None:
        result = _extract_streaming_content('{"content": "hello wor')
        assert result == "hello wor"

    def test_returns_complete_content(self) -> None:
        result = _extract_streaming_content('{"content": "hello world"}')
        assert result == "hello world"

    def test_handles_newline_escape(self) -> None:
        result = _extract_streaming_content('{"content": "line1\\nline2"}')
        assert result == "line1\nline2"

    def test_handles_tab_escape(self) -> None:
        result = _extract_streaming_content('{"content": "col1\\tcol2"}')
        assert result == "col1\tcol2"

    def test_handles_quote_escape(self) -> None:
        result = _extract_streaming_content('{"content": "say \\"hi\\""}')
        assert result == 'say "hi"'

    def test_handles_backslash_escape(self) -> None:
        result = _extract_streaming_content('{"content": "path\\\\file"}')
        assert result == "path\\file"

    def test_handles_slash_escape(self) -> None:
        result = _extract_streaming_content('{"content": "a\\/b"}')
        assert result == "a/b"

    def test_handles_unicode_escape(self) -> None:
        result = _extract_streaming_content('{"content": "caf\\u00e9"}')
        assert result == "caf\u00e9"

    def test_handles_carriage_return_escape(self) -> None:
        result = _extract_streaming_content('{"content": "a\\rb"}')
        assert result == "a\rb"

    def test_incomplete_unicode_escape_stops(self) -> None:
        result = _extract_streaming_content('{"content": "caf\\u00')
        assert result == "caf"

    def test_content_key_with_whitespace(self) -> None:
        result = _extract_streaming_content('{ "content" : "hello" }')
        assert result == "hello"

    def test_content_key_with_preceding_fields(self) -> None:
        result = _extract_streaming_content('{"title": "Test", "content": "body text')
        assert result == "body text"

    def test_returns_none_when_colon_missing(self) -> None:
        result = _extract_streaming_content('"content" "hello"')
        assert result is None

    def test_returns_none_when_quote_missing_after_colon(self) -> None:
        result = _extract_streaming_content('"content": 42')
        assert result is None

    def test_incremental_accumulation(self) -> None:
        """Simulate how content accumulates during streaming."""
        chunks = ['{"title": "T", ', '"content"', ': "', "hel", "lo w", 'orld"}']
        accumulated = ""
        results = []
        for chunk in chunks:
            accumulated += chunk
            results.append(_extract_streaming_content(accumulated))

        assert results[0] is None  # no "content" key yet
        assert results[1] is None  # "content" key seen but no colon+quote
        assert results[2] == ""  # opening quote seen, empty content
        assert results[3] == "hel"
        assert results[4] == "hello w"
        assert results[5] == "hello world"
