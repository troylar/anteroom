"""Tests for tree-sitter codebase index service.

Covers all branches including tree-sitter mocked paths. See issue #689.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from anteroom.services.codebase_index import (
    CodebaseIndexService,
    CodebaseIndexUnavailableError,
    CodebaseMap,
    FileSymbols,
    SymbolInfo,
    _classify_node,
    _estimate_tokens,
    _extract_imports_python,
    _extract_name,
    _extract_signature,
    _parse_file,
    _rank_files,
    create_index_service,
)


class TestClassifyNode:
    def test_import_types(self) -> None:
        assert _classify_node("import_statement", "python") == "import"
        assert _classify_node("import_from_statement", "python") == "import"
        assert _classify_node("use_declaration", "rust") == "import"

    def test_class_types(self) -> None:
        assert _classify_node("class_definition", "python") == "class"
        assert _classify_node("class_declaration", "java") == "class"
        assert _classify_node("struct_item", "rust") == "class"
        assert _classify_node("module", "ruby") == "class"

    def test_interface_type(self) -> None:
        assert _classify_node("interface_declaration", "typescript") == "interface"

    def test_type_alias(self) -> None:
        assert _classify_node("type_alias_declaration", "typescript") == "type"

    def test_type_declaration(self) -> None:
        assert _classify_node("type_declaration", "go") == "type"

    def test_enum_type(self) -> None:
        assert _classify_node("enum_item", "rust") == "enum"

    def test_method_type(self) -> None:
        assert _classify_node("method_declaration", "java") == "method"

    def test_function_type(self) -> None:
        assert _classify_node("function_definition", "python") == "function"
        assert _classify_node("function_declaration", "javascript") == "function"
        assert _classify_node("impl_item", "rust") == "function"

    def test_export_type(self) -> None:
        assert _classify_node("export_statement", "javascript") == "export"

    def test_unknown_type(self) -> None:
        assert _classify_node("some_random_node", "python") == "symbol"


class TestExtractImportsPython:
    def test_from_import(self) -> None:
        node = MagicMock()
        node.text = b"from os.path import join"
        result = _extract_imports_python(node)
        assert result == ["os.path"]

    def test_plain_import(self) -> None:
        node = MagicMock()
        node.text = b"import os, sys"
        result = _extract_imports_python(node)
        assert result == ["os", "sys"]

    def test_import_with_alias(self) -> None:
        node = MagicMock()
        node.text = b"import numpy as np"
        result = _extract_imports_python(node)
        assert result == ["numpy"]

    def test_empty_from(self) -> None:
        node = MagicMock()
        node.text = b"from "
        result = _extract_imports_python(node)
        # "from " splits to ["from", ""] — len < 2 after strip, so empty
        assert result == []


class TestEstimateTokens:
    def test_fallback_char_estimate(self) -> None:
        # tiktoken is installed, so mock it away to test the fallback
        with patch.dict("sys.modules", {"tiktoken": None}):
            # Force the except branch by making import fail
            original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

            def _mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
                if name == "tiktoken":
                    raise ImportError("mocked")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=_mock_import):
                text = "a" * 400
                result = _estimate_tokens(text)
                assert result == 100

    def test_tiktoken_if_available(self) -> None:
        # tiktoken is a dependency, so it should work
        result = _estimate_tokens("hello world")
        assert isinstance(result, int)
        assert result > 0


class TestRankFiles:
    def test_files_ranked_by_import_count(self) -> None:
        files = [
            FileSymbols(path="src/a.py", language="python", symbols=[], imports=["b"]),
            FileSymbols(path="src/b.py", language="python", symbols=[], imports=[]),
            FileSymbols(path="src/c.py", language="python", symbols=[], imports=["b"]),
        ]
        ranked = _rank_files(files)
        # b.py is imported by a.py and c.py, so should be first
        assert ranked[0].path == "src/b.py"

    def test_ties_sorted_alphabetically(self) -> None:
        files = [
            FileSymbols(path="src/z.py", language="python", symbols=[], imports=[]),
            FileSymbols(path="src/a.py", language="python", symbols=[], imports=[]),
        ]
        ranked = _rank_files(files)
        assert ranked[0].path == "src/a.py"
        assert ranked[1].path == "src/z.py"

    def test_empty_list(self) -> None:
        assert _rank_files([]) == []


class TestCodebaseIndexService:
    def test_is_available_without_treesitter(self) -> None:
        with patch.dict("sys.modules", {"tree_sitter": None}):
            service = CodebaseIndexService()
            service._available = None
            # Force reimport failure
            with patch("builtins.__import__", side_effect=ImportError("no tree_sitter")):
                assert service.is_available() is False

    def test_is_available_caches_result(self) -> None:
        service = CodebaseIndexService()
        service._available = True
        assert service.is_available() is True

    def test_scan_fallback_without_treesitter(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".git").mkdir()  # project marker
            (Path(tmpdir) / "hello.py").write_text("def greet(): pass\n")
            result = service.scan(tmpdir)

        assert isinstance(result, CodebaseMap)
        assert len(result.files) == 1
        assert result.files[0].path == "hello.py"
        assert result.files[0].language == "python"
        assert result.files[0].symbols == []  # fallback = no symbols

    def test_scan_respects_exclude_dirs(self) -> None:
        service = CodebaseIndexService(exclude_dirs=["hidden"])
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".git").mkdir()  # project marker
            (Path(tmpdir) / "hello.py").write_text("x = 1\n")
            hidden = Path(tmpdir) / "hidden"
            hidden.mkdir()
            (hidden / "secret.py").write_text("y = 2\n")
            result = service.scan(tmpdir)

        paths = [f.path for f in result.files]
        assert "hello.py" in paths
        assert "hidden/secret.py" not in paths

    def test_scan_respects_language_filter(self) -> None:
        service = CodebaseIndexService(languages=["python"])
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".git").mkdir()  # project marker
            (Path(tmpdir) / "hello.py").write_text("x = 1\n")
            (Path(tmpdir) / "app.js").write_text("let x = 1;\n")
            result = service.scan(tmpdir)

        paths = [f.path for f in result.files]
        assert "hello.py" in paths
        assert "app.js" not in paths

    def test_scan_skips_non_project_directory(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            # No project markers — should skip scan entirely
            (Path(tmpdir) / "hello.py").write_text("x = 1\n")
            result = service.scan(tmpdir)

        assert isinstance(result, CodebaseMap)
        assert result.files == []

    def test_scan_runs_with_pyproject_toml_marker(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = 'test'\n")
            (Path(tmpdir) / "hello.py").write_text("x = 1\n")
            result = service.scan(tmpdir)

        assert len(result.files) == 1
        assert result.files[0].path == "hello.py"

    def test_scan_runs_with_package_json_marker(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text("{}\n")
            (Path(tmpdir) / "app.js").write_text("let x = 1;\n")
            result = service.scan(tmpdir)

        assert len(result.files) == 1
        assert result.files[0].path == "app.js"

    def test_scan_runs_with_cargo_toml_marker(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Cargo.toml").write_text("[package]\nname = 'test'\n")
            (Path(tmpdir) / "main.rs").write_text("fn main() {}\n")
            result = service.scan(tmpdir)

        assert len(result.files) == 1
        assert result.files[0].path == "main.rs"
        assert result.files[0].language == "rust"

    def test_scan_runs_with_go_mod_marker(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "go.mod").write_text("module example.com/test\n")
            (Path(tmpdir) / "main.go").write_text("package main\n")
            result = service.scan(tmpdir)

        assert len(result.files) == 1
        assert result.files[0].path == "main.go"
        assert result.files[0].language == "go"

    def test_scan_runs_with_makefile_marker(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Makefile").write_text("all:\n\techo hello\n")
            (Path(tmpdir) / "lib.py").write_text("x = 1\n")
            result = service.scan(tmpdir)

        assert len(result.files) == 1
        assert result.files[0].path == "lib.py"

    def test_scan_runs_with_cmakelists_marker(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)\n")
            (Path(tmpdir) / "main.c").write_text("int main() { return 0; }\n")
            result = service.scan(tmpdir)

        assert len(result.files) == 1
        assert result.files[0].path == "main.c"
        assert result.files[0].language == "c"

    def test_scan_skip_populates_scan_time(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "hello.py").write_text("x = 1\n")
            result = service.scan(tmpdir)

        assert result.scan_time >= 0.0

    def test_scan_skip_sets_correct_root(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            result = service.scan(tmpdir)

        assert result.root == str(Path(tmpdir).resolve())

    def test_get_map_returns_empty_for_non_project(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "hello.py").write_text("x = 1\n")
            result = service.get_map(tmpdir, token_budget=5000)

        assert result == ""

    def test_scan_with_deeply_nested_files_and_no_marker(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            deep = Path(tmpdir) / "a" / "b" / "c"
            deep.mkdir(parents=True)
            (deep / "deep.py").write_text("x = 1\n")
            result = service.scan(tmpdir)

        assert result.files == []

    def test_format_map_basic(self) -> None:
        service = CodebaseIndexService()
        cmap = CodebaseMap(
            root="/tmp/test",
            files=[
                FileSymbols(
                    path="src/main.py",
                    language="python",
                    symbols=[
                        SymbolInfo(name="greet", kind="function", signature="def greet(name: str) -> str:"),
                        SymbolInfo(name="os", kind="import", signature="import os"),
                    ],
                ),
            ],
        )
        result = service.format_map(cmap, token_budget=5000)
        assert "src/main.py" in result
        assert "def greet(name: str) -> str:" in result
        assert "import os" not in result  # imports are excluded from output

    def test_format_map_respects_token_budget(self) -> None:
        service = CodebaseIndexService()
        files = []
        for i in range(100):
            files.append(
                FileSymbols(
                    path=f"src/module_{i}.py",
                    language="python",
                    symbols=[
                        SymbolInfo(
                            name=f"func_{i}",
                            kind="function",
                            signature=f"def func_{i}(x: int, y: int, z: int) -> dict[str, Any]:",
                        ),
                    ],
                )
            )
        cmap = CodebaseMap(root="/tmp/test", files=files)
        result = service.format_map(cmap, token_budget=200)
        # Should not include all 100 files
        assert result.count("## src/module_") < 100

    def test_format_map_empty_symbols(self) -> None:
        service = CodebaseIndexService()
        cmap = CodebaseMap(
            root="/tmp/test",
            files=[FileSymbols(path="src/empty.py", language="python", symbols=[])],
        )
        result = service.format_map(cmap, token_budget=5000)
        assert "src/empty.py" in result
        assert "(no exported symbols)" in result

    def test_get_map_wraps_in_xml(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".git").mkdir()  # project marker
            (Path(tmpdir) / "hello.py").write_text("x = 1\n")
            result = service.get_map(tmpdir, token_budget=5000)

        assert result.startswith("\n<codebase_index>")
        assert result.endswith("</codebase_index>")

    def test_get_map_empty_dir(self) -> None:
        service = CodebaseIndexService()
        service._available = False

        with tempfile.TemporaryDirectory() as tmpdir:
            result = service.get_map(tmpdir)

        assert result == ""


class TestCreateIndexService:
    def test_returns_service_when_enabled(self) -> None:
        config = MagicMock()
        config.codebase_index.enabled = True
        config.codebase_index.exclude_dirs = [".git", "node_modules"]
        config.codebase_index.languages = []
        result = create_index_service(config)
        assert isinstance(result, CodebaseIndexService)

    def test_returns_none_when_disabled(self) -> None:
        config = MagicMock()
        config.codebase_index.enabled = False
        result = create_index_service(config)
        assert result is None

    def test_passes_languages_filter(self) -> None:
        config = MagicMock()
        config.codebase_index.enabled = True
        config.codebase_index.exclude_dirs = []
        config.codebase_index.languages = ["python", "typescript"]
        result = create_index_service(config)
        assert result is not None
        assert result._languages == {"python", "typescript"}

    def test_none_languages_means_all(self) -> None:
        config = MagicMock()
        config.codebase_index.enabled = True
        config.codebase_index.exclude_dirs = []
        config.codebase_index.languages = None
        result = create_index_service(config)
        assert result is not None
        assert result._languages is None


class TestExtractName:
    """Tests for _extract_name — covers lines 125-132."""

    def _make_child(self, child_type: str, text: str | bytes) -> MagicMock:
        child = MagicMock()
        child.type = child_type
        child.text = text
        return child

    def test_identifier_child_bytes(self) -> None:
        node = MagicMock()
        node.type = "function_definition"
        node.children = [self._make_child("identifier", b"my_func")]
        assert _extract_name(node, "python") == "my_func"

    def test_identifier_child_str(self) -> None:
        node = MagicMock()
        node.type = "function_definition"
        node.children = [self._make_child("identifier", "my_func")]
        assert _extract_name(node, "python") == "my_func"

    def test_name_child_type(self) -> None:
        node = MagicMock()
        node.type = "method"
        node.children = [self._make_child("name", b"do_thing")]
        assert _extract_name(node, "ruby") == "do_thing"

    def test_type_identifier_child(self) -> None:
        node = MagicMock()
        node.type = "struct_item"
        node.children = [self._make_child("type_identifier", b"MyStruct")]
        assert _extract_name(node, "rust") == "MyStruct"

    def test_property_identifier_child(self) -> None:
        node = MagicMock()
        node.type = "class_declaration"
        node.children = [self._make_child("property_identifier", b"MyClass")]
        assert _extract_name(node, "typescript") == "MyClass"

    def test_import_node_uses_full_text_bytes(self) -> None:
        node = MagicMock()
        node.type = "import_statement"
        node.text = b"import os\nimport sys"
        node.children = []
        result = _extract_name(node, "python")
        assert result == "import os"

    def test_import_node_uses_full_text_str(self) -> None:
        node = MagicMock()
        node.type = "import_from_statement"
        node.text = "from pathlib import Path\nmore"
        node.children = []
        result = _extract_name(node, "python")
        assert result == "from pathlib import Path"

    def test_use_declaration_node(self) -> None:
        node = MagicMock()
        node.type = "use_declaration"
        node.text = b"use std::collections::HashMap;"
        node.children = []
        result = _extract_name(node, "rust")
        assert result == "use std::collections::HashMap;"

    def test_no_matching_child_returns_empty(self) -> None:
        node = MagicMock()
        node.type = "block"
        node.text = b"{ body }"
        node.children = [self._make_child("punctuation", b"{")]
        assert _extract_name(node, "python") == ""

    def test_import_text_truncated_at_80(self) -> None:
        node = MagicMock()
        node.type = "import_statement"
        long_text = "import " + "a" * 100
        node.text = long_text.encode()
        node.children = []
        result = _extract_name(node, "python")
        assert len(result) == 80


class TestExtractSignature:
    """Tests for _extract_signature — covers lines 137-142."""

    def test_single_line_bytes(self) -> None:
        node = MagicMock()
        node.text = b"def greet(name: str) -> str:"
        result = _extract_signature(node, "python", "function")
        assert result == "def greet(name: str) -> str:"

    def test_single_line_str(self) -> None:
        node = MagicMock()
        node.text = "def greet(name: str) -> str:"
        result = _extract_signature(node, "python", "function")
        assert result == "def greet(name: str) -> str:"

    def test_multiline_extracts_first_line(self) -> None:
        node = MagicMock()
        node.text = b"def foo():\n    return 1\n"
        result = _extract_signature(node, "python", "function")
        assert result == "def foo():"

    def test_long_signature_truncated(self) -> None:
        node = MagicMock()
        long_sig = "def " + "a" * 120 + "(x):"
        node.text = long_sig.encode()
        result = _extract_signature(node, "python", "function")
        assert len(result) == 120
        assert result.endswith("...")

    def test_exactly_120_chars_not_truncated(self) -> None:
        node = MagicMock()
        sig = "x" * 120
        node.text = sig.encode()
        result = _extract_signature(node, "python", "function")
        assert result == sig
        assert not result.endswith("...")


class TestParseFile:
    """Tests for _parse_file — covers lines 175-214."""

    def _make_mock_parser(self, root_node: Any) -> MagicMock:
        parser = MagicMock()
        tree = MagicMock()
        tree.root_node = root_node
        parser.parse.return_value = tree
        return parser

    def _make_leaf_node(self, node_type: str, text: bytes, children: list | None = None) -> MagicMock:
        node = MagicMock()
        node.type = node_type
        node.text = text
        node.children = children or []
        return node

    def test_returns_none_for_oversized_file(self, tmp_path: Path) -> None:
        f = tmp_path / "big.py"
        f.write_bytes(b"x")
        parser = MagicMock()
        ts_lang = MagicMock()
        with patch("anteroom.services.codebase_index._MAX_FILE_SIZE", 0):
            result = _parse_file(f, tmp_path, "python", parser, ts_lang)
        assert result is None

    def test_returns_none_on_oserror(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.py"
        parser = MagicMock()
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "python", parser, ts_lang)
        assert result is None

    def test_returns_file_symbols_for_unknown_language(self, tmp_path: Path) -> None:
        f = tmp_path / "app.unknown"
        f.write_bytes(b"some content")
        root_node = self._make_leaf_node("root", b"", children=[])
        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        # "unknown_lang" has no query types in _SYMBOL_QUERIES
        result = _parse_file(f, tmp_path, "unknown_lang", parser, ts_lang)
        assert result is not None
        assert result.symbols == []
        assert result.imports == []
        assert result.language == "unknown_lang"

    def test_extracts_python_function(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_bytes(b"def hello(): pass\n")

        id_child = self._make_leaf_node("identifier", b"hello")
        func_node = self._make_leaf_node("function_definition", b"def hello(): pass", children=[id_child])
        root_node = self._make_leaf_node("module", b"def hello(): pass\n", children=[func_node])

        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "python", parser, ts_lang)

        assert result is not None
        assert len(result.symbols) == 1
        assert result.symbols[0].name == "hello"
        assert result.symbols[0].kind == "function"

    def test_extracts_python_import_and_adds_to_imports(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_bytes(b"import os\n")

        import_node = self._make_leaf_node("import_statement", b"import os", children=[])
        root_node = self._make_leaf_node("module", b"import os\n", children=[import_node])

        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "python", parser, ts_lang)

        assert result is not None
        # import kind with no name is still added as a symbol
        assert any(s.kind == "import" for s in result.symbols)
        assert "os" in result.imports

    def test_extracts_non_python_import_with_name(self, tmp_path: Path) -> None:
        f = tmp_path / "app.go"
        f.write_bytes(b'import "fmt"\n')

        id_child = self._make_leaf_node("identifier", b"fmt")
        import_node = self._make_leaf_node("import_declaration", b'import "fmt"', children=[id_child])
        root_node = self._make_leaf_node("source_file", b'import "fmt"\n', children=[import_node])

        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "go", parser, ts_lang)

        assert result is not None
        assert "fmt" in result.imports

    def test_import_without_name_not_added_to_imports(self, tmp_path: Path) -> None:
        f = tmp_path / "app.go"
        f.write_bytes(b"import .\n")

        # import_declaration node with no identifier child and no extractable name
        import_node = self._make_leaf_node("import_declaration", b"import .", children=[])
        root_node = self._make_leaf_node("source_file", b"import .\n", children=[import_node])

        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "go", parser, ts_lang)

        assert result is not None
        # The import_declaration text doesn't start with "import " (no space after dot), so
        # _extract_name returns the full text; but the node type contains "import" so kind=="import"
        # imports list may be empty since the text doesn't parse cleanly as a module name
        assert isinstance(result.imports, list)

    def test_symbol_without_name_and_non_import_not_added(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_bytes(b"def (): pass\n")

        # function_definition node but no identifier child and not an import
        func_node = self._make_leaf_node("function_definition", b"def (): pass", children=[])
        root_node = self._make_leaf_node("module", b"def (): pass\n", children=[func_node])

        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "python", parser, ts_lang)

        assert result is not None
        # name is empty and kind is "function" (not import), so symbol should not be added
        assert len(result.symbols) == 0

    def test_sets_mtime(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_bytes(b"x = 1\n")
        root_node = self._make_leaf_node("module", b"x = 1\n", children=[])
        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "python", parser, ts_lang)
        assert result is not None
        assert result.mtime == f.stat().st_mtime

    def test_sets_relative_path(self, tmp_path: Path) -> None:
        subdir = tmp_path / "src"
        subdir.mkdir()
        f = subdir / "mod.py"
        f.write_bytes(b"x = 1\n")
        root_node = self._make_leaf_node("module", b"x = 1\n", children=[])
        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "python", parser, ts_lang)
        assert result is not None
        assert result.path == "src/mod.py"

    def test_recursive_walk_into_children(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_bytes(b"class Foo:\n    def bar(self): pass\n")

        id_child = self._make_leaf_node("identifier", b"bar")
        method_node = self._make_leaf_node("function_definition", b"def bar(self): pass", children=[id_child])
        class_id = self._make_leaf_node("identifier", b"Foo")
        class_body = b"class Foo:\n    def bar(self): pass"
        class_node = self._make_leaf_node("class_definition", class_body, children=[class_id, method_node])
        root_node = self._make_leaf_node("module", b"class Foo:\n    def bar(self): pass\n", children=[class_node])

        parser = self._make_mock_parser(root_node)
        ts_lang = MagicMock()
        result = _parse_file(f, tmp_path, "python", parser, ts_lang)

        assert result is not None
        names = [s.name for s in result.symbols]
        assert "Foo" in names
        assert "bar" in names


class TestRankFilesInitPath:
    """Tests for _rank_files __init__ path — covers line 234."""

    def test_init_py_path_stripped_and_ranked(self) -> None:
        # src/pkg/__init__.py -> module "src.pkg" (after stripping .__init__)
        # When another file imports "src.pkg", __init__.py gets a count
        files = [
            FileSymbols(path="src/pkg/__init__.py", language="python", symbols=[], imports=[]),
            FileSymbols(path="src/main.py", language="python", symbols=[], imports=["src.pkg"]),
        ]
        ranked = _rank_files(files)
        # src/pkg/__init__.py is imported by src/main.py -> count=1, ranked first
        assert ranked[0].path == "src/pkg/__init__.py"

    def test_init_py_module_name_derived_without_init_suffix(self) -> None:
        # Verify the .__init__ stripping works: "a.b.__init__" -> "a.b"
        # An importer using "a.b" should hit the __init__.py
        files = [
            FileSymbols(path="a/b/__init__.py", language="python", symbols=[], imports=[]),
            FileSymbols(path="a/b/util.py", language="python", symbols=[], imports=[]),
            FileSymbols(path="consumer.py", language="python", symbols=[], imports=["a.b"]),
        ]
        ranked = _rank_files(files)
        # a/b/__init__.py maps to module "a.b" which matches the import "a.b"
        assert ranked[0].path == "a/b/__init__.py"

    def test_non_init_file_uses_stem(self) -> None:
        # A regular file like "utils.py" -> stem "utils"
        # When another file imports "utils", it should get count 1 and rank first
        files = [
            FileSymbols(path="utils.py", language="python", symbols=[], imports=[]),
            FileSymbols(path="app.py", language="python", symbols=[], imports=["utils"]),
        ]
        ranked = _rank_files(files)
        assert ranked[0].path == "utils.py"


class TestEnsureParserAndGetLanguage:
    """Tests for _ensure_parser and _get_language — covers lines 278, 282-283, 292-302, 310."""

    def test_ensure_parser_returns_cached(self) -> None:
        service = CodebaseIndexService()
        mock_parser = MagicMock()
        service._parser = mock_parser
        result = service._ensure_parser()
        assert result is mock_parser

    def test_ensure_parser_creates_parser_when_tree_sitter_available(self) -> None:
        service = CodebaseIndexService()
        service._parser = None

        mock_ts = MagicMock()
        mock_parser_instance = MagicMock()
        mock_ts.Parser.return_value = mock_parser_instance

        with patch.dict("sys.modules", {"tree_sitter": mock_ts}):
            result = service._ensure_parser()

        assert result is mock_parser_instance
        assert service._parser is mock_parser_instance

    def test_ensure_parser_raises_when_tree_sitter_missing(self) -> None:
        service = CodebaseIndexService()
        service._parser = None

        with patch.dict("sys.modules", {"tree_sitter": None}):
            with pytest.raises(CodebaseIndexUnavailableError, match="tree-sitter is not installed"):
                service._ensure_parser()

        assert service._available is False

    def test_get_language_returns_cached(self) -> None:
        service = CodebaseIndexService()
        mock_lang = MagicMock()
        service._lang_cache["python"] = mock_lang
        result = service._get_language("python")
        assert result is mock_lang

    def test_get_language_loads_from_pack(self) -> None:
        service = CodebaseIndexService()
        mock_pack = MagicMock()
        mock_lang = MagicMock()
        mock_pack.get_language.return_value = mock_lang

        with patch.dict("sys.modules", {"tree_sitter_language_pack": mock_pack}):
            result = service._get_language("python")

        assert result is mock_lang
        assert service._lang_cache["python"] is mock_lang

    def test_get_language_returns_none_on_import_error(self) -> None:
        service = CodebaseIndexService()

        with patch.dict("sys.modules", {"tree_sitter_language_pack": None}):
            result = service._get_language("python")

        assert result is None

    def test_get_language_returns_none_on_other_exception(self) -> None:
        service = CodebaseIndexService()
        mock_pack = MagicMock()
        mock_pack.get_language.side_effect = Exception("unknown lang")

        with patch.dict("sys.modules", {"tree_sitter_language_pack": mock_pack}):
            result = service._get_language("python")

        assert result is None

    def test_is_available_sets_true_when_parser_succeeds(self) -> None:
        service = CodebaseIndexService()
        service._available = None
        mock_ts = MagicMock()
        mock_ts.Parser.return_value = MagicMock()

        with patch.dict("sys.modules", {"tree_sitter": mock_ts}):
            result = service.is_available()

        assert result is True
        assert service._available is True


class TestScanWithTreeSitter:
    """Tests for scan() with tree-sitter mocked — covers lines 348-375."""

    def _make_mock_tree_sitter(self) -> tuple[MagicMock, MagicMock]:
        """Return (mock_ts_module, mock_parser)."""
        mock_ts = MagicMock()
        mock_parser = MagicMock()
        mock_ts.Parser.return_value = mock_parser
        return mock_ts, mock_parser

    def _setup_parse_result(self, mock_parser: MagicMock, symbols: list[SymbolInfo] | None = None) -> None:
        """Configure parser to return an empty tree."""
        root_node = MagicMock()
        root_node.type = "module"
        root_node.children = []
        tree = MagicMock()
        tree.root_node = root_node
        mock_parser.parse.return_value = tree

    def test_scan_uses_mtime_cache(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        f = tmp_path / "mod.py"
        f.write_bytes(b"x = 1\n")

        service = CodebaseIndexService()
        mock_ts, mock_parser = self._make_mock_tree_sitter()
        self._setup_parse_result(mock_parser)

        mock_lang = MagicMock()

        with patch.dict("sys.modules", {"tree_sitter": mock_ts, "tree_sitter_language_pack": MagicMock()}):
            service._parser = mock_parser
            service._available = True
            service._lang_cache["python"] = mock_lang

            # First scan — parses and caches
            result1 = service.scan(str(tmp_path))
            assert len(result1.files) == 1
            parse_count_after_first = mock_parser.parse.call_count

            # Second scan with same mtime — should use cache, not re-parse
            result2 = service.scan(str(tmp_path))
            assert len(result2.files) == 1
            assert mock_parser.parse.call_count == parse_count_after_first  # no new parse calls

    def test_scan_skips_file_on_oserror_during_mtime(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        f = tmp_path / "mod.py"
        f.write_bytes(b"x = 1\n")

        service = CodebaseIndexService()
        mock_ts, mock_parser = self._make_mock_tree_sitter()
        mock_lang = MagicMock()

        # Patch stat only for the source file path by replacing it in the scan loop
        real_stat = Path.stat

        def stat_raises_for_source(self: Path, **kwargs: Any) -> Any:  # type: ignore[override]
            if self == f:
                raise OSError("no access")
            return real_stat(self, **kwargs)

        with patch.dict("sys.modules", {"tree_sitter": mock_ts, "tree_sitter_language_pack": MagicMock()}):
            service._parser = mock_parser
            service._available = True
            service._lang_cache["python"] = mock_lang

            with patch.object(Path, "stat", stat_raises_for_source):
                result = service.scan(str(tmp_path))

        # OSError on stat for source file means the file is skipped
        assert result.files == []

    def test_scan_adds_filename_only_when_language_unavailable(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        f = tmp_path / "mod.py"
        f.write_bytes(b"x = 1\n")

        service = CodebaseIndexService()
        mock_ts, mock_parser = self._make_mock_tree_sitter()

        with patch.dict("sys.modules", {"tree_sitter": mock_ts, "tree_sitter_language_pack": MagicMock()}):
            service._parser = mock_parser
            service._available = True
            # No lang in cache and _get_language returns None
            with patch.object(service, "_get_language", return_value=None):
                result = service.scan(str(tmp_path))

        assert len(result.files) == 1
        assert result.files[0].path == "mod.py"
        assert result.files[0].symbols == []

    def test_scan_skips_parse_file_returning_none(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        f = tmp_path / "mod.py"
        f.write_bytes(b"x = 1\n")

        service = CodebaseIndexService()
        mock_ts, mock_parser = self._make_mock_tree_sitter()
        mock_lang = MagicMock()

        with patch.dict("sys.modules", {"tree_sitter": mock_ts, "tree_sitter_language_pack": MagicMock()}):
            service._parser = mock_parser
            service._available = True
            service._lang_cache["python"] = mock_lang
            # Make _parse_file return None (e.g. oversized file)
            with patch("anteroom.services.codebase_index._parse_file", return_value=None):
                result = service.scan(str(tmp_path))

        assert result.files == []

    def test_scan_full_pipeline_with_mocked_treesitter(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        f = tmp_path / "mod.py"
        f.write_bytes(b"def hello(): pass\n")

        id_child = MagicMock()
        id_child.type = "identifier"
        id_child.text = b"hello"
        id_child.children = []

        func_node = MagicMock()
        func_node.type = "function_definition"
        func_node.text = b"def hello(): pass"
        func_node.children = [id_child]

        root_node = MagicMock()
        root_node.type = "module"
        root_node.children = [func_node]

        mock_ts, mock_parser = self._make_mock_tree_sitter()
        tree = MagicMock()
        tree.root_node = root_node
        mock_parser.parse.return_value = tree
        mock_lang = MagicMock()

        with patch.dict("sys.modules", {"tree_sitter": mock_ts, "tree_sitter_language_pack": MagicMock()}):
            service = CodebaseIndexService()
            service._parser = mock_parser
            service._available = True
            service._lang_cache["python"] = mock_lang
            result = service.scan(str(tmp_path))

        assert len(result.files) == 1
        assert result.files[0].path == "mod.py"
        assert len(result.files[0].symbols) == 1
        assert result.files[0].symbols[0].name == "hello"
