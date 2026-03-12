from __future__ import annotations

import asyncio
import builtins
import tempfile
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, AsyncGenerator, Callable
from unittest.mock import patch

import prompt_toolkit

from anteroom.cli import renderer
from anteroom.cli.repl import run_cli
from anteroom.config import AIConfig, AppConfig, AppSettings, EmbeddingsConfig
from anteroom.db import get_db, init_db
from anteroom.services import storage
from anteroom.services.ai_service import AIService
from anteroom.tools.safety import SafetyVerdict


class _BufferEvents(list):
    def __iadd__(self, other):
        self.append(other)
        return self


class _Buffer:
    def __init__(self) -> None:
        self.on_text_changed = _BufferEvents()


class _PromptQueues:
    def __init__(
        self,
        *,
        main_inputs: list[tuple[float, str | BaseException]],
        confirm_inputs: list[tuple[float, str | BaseException]] | None = None,
        ask_inputs: list[tuple[float, str | BaseException]] | None = None,
        raw_inputs: list[tuple[float, str | BaseException]] | None = None,
    ) -> None:
        self._main_inputs = iter(main_inputs)
        self._confirm_inputs = iter(confirm_inputs or [])
        self._ask_inputs = iter(ask_inputs or [])
        self._raw_inputs = iter(raw_inputs or [])

    def next_input(self, prompt_kind: str) -> tuple[float, str | BaseException]:
        if prompt_kind == "confirm":
            source = self._confirm_inputs
        elif prompt_kind == "ask":
            source = self._ask_inputs
        elif prompt_kind == "raw":
            source = self._raw_inputs
        else:
            source = self._main_inputs
        try:
            return next(source)
        except StopIteration:
            raise EOFError from None


class _ScriptedPromptSession:
    def __init__(self, script: _PromptQueues) -> None:
        self._script = script
        self.default_buffer = _Buffer()

    async def prompt_async(self, *args, **kwargs) -> str:
        prompt_text = args[0] if args else ""
        if isinstance(prompt_text, str) and "Allow once" in prompt_text:
            prompt_kind = "confirm"
        elif isinstance(prompt_text, str) and ("Choice:" in prompt_text or "Answer:" in prompt_text):
            prompt_kind = "ask"
        else:
            prompt_kind = "main"
        try:
            delay, text = self._script.next_input(prompt_kind)
        except EOFError:
            await asyncio.Future()
            raise AssertionError("unreachable")
        for callback in self.default_buffer.on_text_changed:
            callback(self.default_buffer)
        await asyncio.sleep(delay)
        if isinstance(text, BaseException):
            raise text
        return text


async def _run_legacy_session(
    tmp_path: Path,
    *,
    scripted_inputs: (
        list[tuple[float, str | BaseException]]
        | list[str]
        | Callable[[Any], list[tuple[float, str | BaseException]] | list[str]]
    ),
    confirm_inputs: list[tuple[float, str | BaseException]] | list[str] | None = None,
    ask_inputs: list[tuple[float, str | BaseException]] | list[str] | None = None,
    raw_inputs: list[tuple[float, str | BaseException]] | list[str] | None = None,
    seed_db: Callable[[Any], Any] | None = None,
    stream_factory: Callable[..., AsyncGenerator[dict[str, Any], None]] | None = None,
) -> str:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db = init_db(data_dir / "chat.db")
    seed_result = seed_db(db) if seed_db is not None else None
    db.close()

    config = AppConfig(
        ai=AIConfig(base_url="http://localhost:1/v1", api_key="test-key", model="gpt-5.2"),
        app=AppSettings(data_dir=data_dir),
        embeddings=EmbeddingsConfig(enabled=False),
    )

    raw_inputs = scripted_inputs(seed_result) if callable(scripted_inputs) else scripted_inputs
    normalized_inputs = [item if isinstance(item, tuple) else (0.0, item) for item in raw_inputs]
    normalized_confirm = [
        item if isinstance(item, tuple) else (0.0, item) for item in (confirm_inputs or [])
    ]
    normalized_ask = [item if isinstance(item, tuple) else (0.0, item) for item in (ask_inputs or [])]
    normalized_raw = [item if isinstance(item, tuple) else (0.0, item) for item in (raw_inputs or [])]
    prompt_script = _PromptQueues(
        main_inputs=list(normalized_inputs),
        confirm_inputs=list(normalized_confirm),
        ask_inputs=list(normalized_ask),
        raw_inputs=list(normalized_raw),
    )

    def _session_factory(*args, **kwargs):
        return _ScriptedPromptSession(prompt_script)

    def _raw_input(prompt_text: str = "") -> str:
        del prompt_text
        delay, text = prompt_script.next_input("raw")
        if delay:
            import time

            time.sleep(delay)
        if isinstance(text, BaseException):
            raise text
        return text

    stdout_file = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    try:
        renderer._stdout = stdout_file
        renderer._stdout_console = renderer.Console(file=stdout_file, force_terminal=False, color_system=None)
        renderer._stdout_is_tty = False
        with (
            patch.object(
                AIService,
                "validate_connection",
                new=lambda self, _token_refreshed=False: asyncio.sleep(0, result=(True, "ok", ["gpt-5.2"])),
            ),
            patch.object(AIService, "stream_chat", new=stream_factory) if stream_factory is not None else nullcontext(),
            patch("anteroom.cli.repl._check_for_update", new=lambda current: asyncio.sleep(0, result=None)),
            patch.object(prompt_toolkit, "PromptSession", new=_session_factory),
            patch.object(builtins, "input", new=_raw_input),
            patch("prompt_toolkit.patch_stdout.patch_stdout", new=lambda *args, **kwargs: nullcontext()),
            redirect_stdout(stdout_file),
            redirect_stderr(stdout_file),
        ):
            await run_cli(config, ui="legacy", no_project_context=True)

        stdout_file.seek(0)
        return stdout_file.read()
    finally:
        renderer.console = renderer.Console(stderr=True)
        renderer._stdout_console = renderer.Console()
        renderer._stdout = renderer.sys.stdout
        renderer._stdout_is_tty = True
        renderer._repl_mode = False
        stdout_file.close()


async def test_legacy_cli_lists_conversations_starts_note_and_lists_skills(tmp_path: Path) -> None:
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[
            (0.0, "/list 5"),
            (0.1, "/new note Architecture Notes"),
            (0.1, "/skills"),
            (0.25, "/quit"),
        ],
    )

    assert "Recent conversations:" in output
    assert "New Conversation" in output
    assert "Available skills:" in output

    db = get_db(tmp_path / "data" / "chat.db")
    try:
        conversations = storage.list_conversations(db, limit=20)
    finally:
        db.close()

    assert any(
        c["title"] == "Architecture Notes" and c.get("type") == "note"
        for c in conversations
    )


async def test_legacy_cli_rename_updates_persisted_current_conversation(tmp_path: Path) -> None:
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[
            (0.0, "/rename Renamed Architecture Notes"),
            (0.1, "/slug"),
            (0.2, "/quit"),
        ],
    )

    assert 'Renamed conversation to "Renamed Architecture Notes"' in output
    assert "Slug:" in output

    db = get_db(tmp_path / "data" / "chat.db")
    try:
        conversations = storage.list_conversations(db, limit=5)
    finally:
        db.close()

    assert conversations[0]["title"] == "Renamed Architecture Notes"


async def test_legacy_cli_usage_command_renders_usage_summary(tmp_path: Path) -> None:
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[(0.0, "/usage"), (0.15, "/quit")],
    )

    assert "Today:" in output
    assert "This week:" in output
    assert "This month:" in output


async def test_legacy_cli_delete_cancel_preserves_target_conversation(tmp_path: Path) -> None:
    def _seed(db: Any) -> str:
        conv = storage.create_conversation(db, title="Delete Me", working_dir=str(tmp_path))
        storage.create_message(db, conv["id"], "user", "keep this conversation")
        return conv["slug"]

    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=lambda conv_slug: [(0.0, f"/delete {conv_slug}"), (0.15, "/quit")],
        raw_inputs=["n"],
        seed_db=_seed,
    )

    assert "Cancelled" in output

    db = get_db(tmp_path / "data" / "chat.db")
    try:
        conversations = storage.list_conversations(db, limit=20)
    finally:
        db.close()

    assert any(conv["title"] == "Delete Me" for conv in conversations)


async def test_legacy_cli_rewind_invalid_position_preserves_message_history(tmp_path: Path) -> None:
    def _seed(db: Any) -> str:
        conv = storage.create_conversation(db, title="Rewind Me", working_dir=str(tmp_path))
        storage.create_message(db, conv["id"], "user", "first question")
        storage.create_message(db, conv["id"], "assistant", "first answer")
        storage.create_message(db, conv["id"], "user", "second question")
        storage.create_message(db, conv["id"], "assistant", "second answer")
        return conv["id"]

    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=lambda conv_id: [(0.0, f"/resume {conv_id}"), (0.1, "/rewind"), (0.25, "/quit")],
        raw_inputs=["bogus"],
        seed_db=_seed,
    )

    assert "Messages:" in output
    assert "Invalid position" in output

    db = get_db(tmp_path / "data" / "chat.db")
    try:
        conversations = storage.list_conversations(db, limit=20)
        conv = next(conv for conv in conversations if conv["title"] == "Rewind Me")
        preserved = storage.list_messages(db, conv["id"])
    finally:
        db.close()

    assert len([msg for msg in preserved if msg["role"] in {"user", "assistant"}]) >= 4


def _retry_then_answer_stream(
    self,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    cancel_event: Any = None,
    extra_system_prompt: str | None = None,
):
    async def _gen():
        yield {"event": "retrying", "data": {"attempt": 2, "max_attempts": 2, "reason": "turn_retry"}}
        yield {"event": "token", "data": {"content": "Recovered from retry. "}}
        yield {"event": "assistant_message", "data": {"content": "Recovered from retry."}}
        yield {"event": "done", "data": {}}

    return _gen()


def _tool_then_answer_stream():
    call_count = 0

    async def _stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        cancel_event: Any = None,
        extra_system_prompt: str | None = None,
    ):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "event": "tool_call",
                "data": {
                    "id": "call_test_legacy_001",
                    "function_name": "grep",
                    "arguments": {"path": "src/", "pattern": "toggle_last_fold"},
                },
            }
            yield {"event": "done", "data": {}}
        else:
            yield {"event": "token", "data": {"content": "Found the symbol in renderer.py. "}}
            yield {
                "event": "assistant_message",
                "data": {"content": "Found the symbol in renderer.py."},
            }
            yield {"event": "done", "data": {}}

    return _stream


def _partial_error_stream(
    self,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    cancel_event: Any = None,
    extra_system_prompt: str | None = None,
):
    async def _gen():
        yield {"event": "token", "data": {"content": "Partial answer"}}
        yield {
            "event": "error",
            "data": {"message": "Stream ended unexpectedly — response may be incomplete", "retryable": False},
        }

    return _gen()


def _approval_then_answer_stream(tool_arguments: dict[str, Any]):
    call_count = 0

    async def _stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        cancel_event: Any = None,
        extra_system_prompt: str | None = None,
    ):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "event": "tool_call",
                "data": {
                    "id": "call_test_legacy_approval_001",
                    "function_name": "bash",
                    "arguments": tool_arguments,
                },
            }
            yield {"event": "done", "data": {}}
        else:
            yield {"event": "token", "data": {"content": "I finished the approved write. "}}
            yield {"event": "assistant_message", "data": {"content": "I finished the approved write."}}
            yield {"event": "done", "data": {}}

    return _stream


def _ask_user_then_answer_stream():
    call_count = 0

    async def _stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        cancel_event: Any = None,
        extra_system_prompt: str | None = None,
    ):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "event": "tool_call",
                "data": {
                    "id": "call_test_legacy_ask_001",
                    "function_name": "ask_user",
                    "arguments": {
                        "question": "Which mode should I use?",
                        "options": ["safe", "fast", "balanced"],
                    },
                },
            }
            yield {"event": "done", "data": {}}
        else:
            yield {"event": "token", "data": {"content": "Using the selected mode now. "}}
            yield {"event": "assistant_message", "data": {"content": "Using the selected mode now."}}
            yield {"event": "done", "data": {}}

    return _stream


async def test_legacy_cli_retry_turn_shows_recovery_and_answer(tmp_path: Path) -> None:
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[(0.0, "who is the president"), (0.2, "/quit")],
        stream_factory=_retry_then_answer_stream,
    )

    assert "Recovered from retry." in output
    assert "AI:" in output


async def test_legacy_cli_tool_turn_shows_working_story_and_answer(tmp_path: Path) -> None:
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[(0.0, 'Search for "toggle_last_fold" in src/'), (0.2, "/quit")],
        stream_factory=_tool_then_answer_stream(),
    )

    assert "Searching for 'toggle_last_fold'" in output
    assert "✓" in output
    assert "AI:" in output
    assert "Found the symbol in renderer.py." in output


async def test_legacy_cli_partial_error_turn_surfaces_error_message(tmp_path: Path) -> None:
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[(0.0, "give me the answer"), (0.2, "/quit")],
        stream_factory=_partial_error_stream,
    )

    assert "Stream ended unexpectedly" in output
    assert "Thinking..." in output


async def test_legacy_cli_approval_prompt_allows_session_and_executes_tool(tmp_path: Path) -> None:
    target_path = tmp_path / "approved.txt"
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[
            (0.0, "Write the approval marker"),
            (0.2, "/quit"),
        ],
        confirm_inputs=["s"],
        stream_factory=_approval_then_answer_stream(
            {"command": f"printf 'approved' > {target_path}", "timeout": 5}
        ),
    )

    assert "Warning:" in output
    assert "Allowed: bash" in output
    assert "session" in output
    assert "I finished the approved write." in output
    assert target_path.read_text() == "approved"


async def test_legacy_cli_approval_prompt_denial_blocks_tool_execution(tmp_path: Path) -> None:
    target_path = tmp_path / "denied.txt"
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[
            (0.0, "Write the denial marker"),
            (0.2, "/quit"),
        ],
        confirm_inputs=["n"],
        stream_factory=_approval_then_answer_stream(
            {"command": f"printf 'denied' > {target_path}", "timeout": 5}
        ),
    )

    assert "Warning:" in output
    assert "Denied: bash" in output
    assert "Allowed: bash" not in output
    assert not target_path.exists()


async def test_legacy_cli_approval_prompt_interrupt_denies_tool_execution(tmp_path: Path) -> None:
    target_path = tmp_path / "interrupted.txt"
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[
            (0.0, "Write the interrupted marker"),
            (0.2, "/quit"),
        ],
        confirm_inputs=[KeyboardInterrupt()],
        stream_factory=_approval_then_answer_stream(
            {"command": f"printf 'interrupted' > {target_path}", "timeout": 5}
        ),
    )

    assert "Warning:" in output
    assert "Denied: bash" in output
    assert "Allowed: bash" not in output
    assert not target_path.exists()


async def test_legacy_cli_ask_user_flow_renders_question_and_selected_option(tmp_path: Path) -> None:
    output = await _run_legacy_session(
        tmp_path,
        scripted_inputs=[
            (0.0, "Help me choose"),
            (0.2, "/quit"),
        ],
        ask_inputs=["2"],
        stream_factory=_ask_user_then_answer_stream(),
    )

    assert "Question:" in output
    assert "Which mode should I use?" in output
    assert "safe" in output
    assert "fast" in output
    assert "balanced" in output
    assert "Using the selected mode now." in output


async def test_textual_cli_handoff_wires_ui_bridge_into_backend(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config = AppConfig(
        ai=AIConfig(base_url="http://localhost:1/v1", api_key="test-key", model="gpt-5.2"),
        app=AppSettings(data_dir=data_dir),
        embeddings=EmbeddingsConfig(enabled=False),
    )

    observed: dict[str, Any] = {}

    async def _fake_run_textual_chat(
        *,
        backend: Any,
        session: Any,
        initial_prompt: str | None,
        ui_bridge: dict[str, Any],
    ):
        observed["initial_prompt"] = initial_prompt
        observed["session_model"] = session.model
        observed["working_dir"] = session.working_dir
        observed["confirm_before"] = ui_bridge.get("confirm")
        observed["ask_before"] = ui_bridge.get("ask")

        async def _confirm(verdict: SafetyVerdict) -> str:
            observed["confirm_verdict"] = verdict
            return "session"

        async def _ask(question: str, options: list[str] | None) -> str:
            observed["ask_question"] = question
            observed["ask_options"] = options
            return "balanced"

        ui_bridge["confirm"] = _confirm
        ui_bridge["ask"] = _ask

        verdict = SafetyVerdict(
            needs_approval=True,
            reason="test confirmation",
            tool_name="bash",
            details={"command": "echo hi"},
        )
        observed["confirm_result"] = await backend.tool_registry._confirm_callback(verdict)
        observed["session_allowed"] = "bash" in backend.tool_registry._session_allowed

        ask_result = await backend.tool_executor(
            "ask_user",
            {"question": "Which mode should I use?", "options": ["safe", "fast", "balanced"]},
        )
        observed["ask_result"] = ask_result

    with (
        patch.object(
            AIService,
            "validate_connection",
            new=lambda self, _token_refreshed=False: asyncio.sleep(0, result=(True, "ok", ["gpt-5.2"])),
        ),
        patch("anteroom.cli.repl._check_for_update", new=lambda current: asyncio.sleep(0, result=None)),
        patch("anteroom.cli.textual_app.run_textual_chat", new=_fake_run_textual_chat),
    ):
        await run_cli(
            config,
            prompt="Explain the CLI state machine",
            ui="textual",
            no_project_context=True,
        )

    assert observed["initial_prompt"] == "Explain the CLI state machine"
    assert observed["session_model"] == "gpt-5.2"
    assert observed["confirm_before"] is None
    assert observed["ask_before"] is None
    assert observed["confirm_result"] is True
    assert observed["session_allowed"] is True
    assert observed["ask_question"] == "Which mode should I use?"
    assert observed["ask_options"] == ["safe", "fast", "balanced"]
    assert observed["ask_result"]["answer"] == "balanced"
