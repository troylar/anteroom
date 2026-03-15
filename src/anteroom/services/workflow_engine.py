"""Workflow engine — load, validate, and execute workflow definitions.

The engine core is domain-neutral. It orchestrates steps (runner, gate, loop)
defined in YAML without knowledge of what domain the workflow serves. Domain-
specific behavior (GitHub issue checks, PR creation, code review) lives in
workflow definitions, gate conditions, and runner adapters — not here.
"""

from __future__ import annotations

import logging
import shlex
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from ..config import WorkflowConfig
    from ..db import ThreadSafeConnection
    from .workflow_runners import RunnerRegistry, RunnerResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Definition dataclasses (domain-neutral)
# ---------------------------------------------------------------------------


@dataclass
class WorkflowStepDef:
    """A single step in a workflow definition. Domain-neutral."""

    id: str
    type: str  # "runner", "gate", "loop"
    # Runner fields (opaque + agent)
    runner: str | None = None
    command: str | None = None  # shell: command string; python_script: script path
    argv: list[str] | None = None  # python_script: positional args
    prompt: str | None = None  # agent runners: user prompt
    system_prompt: str | None = None  # agent runners: system prompt override
    context_from: list[dict[str, str]] | None = None  # artifact refs from prior steps
    tools: list[str] | None = None  # agent runners: tool filter
    env: dict[str, str] | None = None  # additional env vars
    working_dir: str | None = None  # cwd override
    # Gate fields
    condition: str | None = None
    if_false: str | None = None
    # Loop fields
    max_rounds: int | None = None
    steps: list[WorkflowStepDef] | None = None
    # Common
    approval_mode: str | None = None
    timeout: int | None = None


@dataclass
class WorkflowDefinition:
    """A parsed workflow definition. Domain-neutral."""

    id: str
    version: str
    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    policies: dict[str, Any] = field(default_factory=dict)
    steps: list[WorkflowStepDef] = field(default_factory=list)
    notifications: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Gate condition registry (domain-neutral interface)
# ---------------------------------------------------------------------------

GateConditionFn = Any  # Callable[[dict, WorkflowStepDef], Awaitable[bool]]

_gate_registry: dict[str, GateConditionFn] = {}


def register_gate_condition(name: str, fn: GateConditionFn) -> None:
    _gate_registry[name] = fn


def get_gate_condition(name: str) -> GateConditionFn | None:
    return _gate_registry.get(name)


# ---------------------------------------------------------------------------
# Template resolution (domain-neutral)
# ---------------------------------------------------------------------------


def resolve_template(template: str, variables: dict[str, Any], *, shell_quote: bool = False) -> str:
    """Resolve {variable} placeholders from workflow inputs.

    If shell_quote=True, values are passed through shlex.quote() before
    interpolation (used for shell runner commands). Template variables
    must reference declared inputs only — undeclared variables raise KeyError.
    """
    resolved = {}
    for key, val in variables.items():
        str_val = str(val)
        resolved[key] = shlex.quote(str_val) if shell_quote else str_val
    return template.format(**resolved)


def resolve_context_from(
    context_refs: list[dict[str, str]],
    step_results: dict[str, dict[str, Any]],
) -> str:
    """Resolve context_from references into a context string.

    Each ref is {"step": "<step_id>", "field": "<dotted.path>"}.
    step_results maps step_id → step record dict (from storage).
    Returns a newline-joined string of resolved context values.
    """
    parts: list[str] = []
    for ref in context_refs:
        step_id = ref["step"]
        field_path = ref["field"]
        step_data = step_results.get(step_id)
        if step_data is None:
            logger.warning("context_from: step %r not found in results", step_id)
            continue
        value = _resolve_dotted_path(step_data, field_path)
        if value is not None:
            parts.append(f"[{step_id}.{field_path}]\n{value}")
    return "\n\n".join(parts)


def _resolve_dotted_path(data: dict[str, Any], path: str) -> Any:
    """Resolve a dotted field path like 'result_artifacts.pr_number'."""
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


# ---------------------------------------------------------------------------
# Definition loader
# ---------------------------------------------------------------------------


def load_definition(source: str | Path) -> WorkflowDefinition:
    """Load and validate a workflow definition from YAML.

    source can be a file path or a YAML string (for testing).
    """
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and source.endswith(".yaml")):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Workflow definition not found: {path}")
        raw = yaml.safe_load(path.read_text())
    else:
        raw = yaml.safe_load(source)

    if not isinstance(raw, dict):
        raise ValueError("Workflow definition must be a YAML mapping")
    if raw.get("kind") != "workflow":
        raise ValueError(f"Expected kind: workflow, got: {raw.get('kind')!r}")
    if not raw.get("id"):
        raise ValueError("Workflow definition must have an 'id' field")
    if not raw.get("version"):
        raise ValueError("Workflow definition must have a 'version' field")

    steps = [_parse_step(s) for s in raw.get("steps", [])]
    if not steps:
        raise ValueError("Workflow definition must have at least one step")

    defn = WorkflowDefinition(
        id=raw["id"],
        version=raw["version"],
        inputs=raw.get("inputs", {}),
        policies=raw.get("policies", {}),
        steps=steps,
        notifications=raw.get("notifications"),
    )
    _validate_definition(defn)
    return defn


def _parse_step(raw: dict[str, Any]) -> WorkflowStepDef:
    if not raw.get("id"):
        raise ValueError("Each step must have an 'id' field")
    if not raw.get("type"):
        raise ValueError(f"Step {raw['id']!r} must have a 'type' field")
    step_type = raw["type"]
    if step_type not in ("runner", "gate", "loop"):
        raise ValueError(f"Step {raw['id']!r}: invalid type {step_type!r}")

    nested_steps = None
    if step_type == "loop":
        nested_raw = raw.get("steps", [])
        nested_steps = [_parse_step(s) for s in nested_raw]

    return WorkflowStepDef(
        id=raw["id"],
        type=step_type,
        runner=raw.get("runner"),
        command=raw.get("command"),
        argv=raw.get("argv"),
        prompt=raw.get("prompt"),
        system_prompt=raw.get("system_prompt"),
        context_from=raw.get("context_from"),
        tools=raw.get("tools"),
        env=raw.get("env"),
        working_dir=raw.get("working_dir"),
        condition=raw.get("condition"),
        if_false=raw.get("if_false"),
        max_rounds=raw.get("max_rounds"),
        steps=nested_steps,
        approval_mode=raw.get("approval_mode"),
        timeout=raw.get("timeout"),
    )


def _validate_definition(defn: WorkflowDefinition) -> None:
    """Validate step payloads and context_from references at load time.

    Ensures:
    - Shell runner steps have a command
    - Agent runner steps have a prompt
    - Gate steps have a condition
    - context_from references point to steps that appear earlier in execution order
    """
    from .workflow_runners import AGENT_RUNNER_TYPES

    all_steps = _all_steps(defn.steps)
    seen_step_ids: set[str] = set()

    for step in all_steps:
        if step.type == "runner":
            if not step.runner:
                raise ValueError(f"Runner step {step.id!r} has no runner type")
            if step.runner in ("shell",) and not step.command:
                raise ValueError(f"Shell runner step {step.id!r} requires a 'command' field")
            if step.runner == "python_script" and not step.command:
                raise ValueError(f"Python script runner step {step.id!r} requires a 'command' field")
            if step.runner in AGENT_RUNNER_TYPES and not step.prompt:
                raise ValueError(f"Agent runner step {step.id!r} requires a 'prompt' field")
        elif step.type == "gate":
            if not step.condition:
                raise ValueError(f"Gate step {step.id!r} requires a 'condition' field")

        if step.context_from:
            for ref in step.context_from:
                ref_step = ref.get("step")
                if not ref_step:
                    raise ValueError(f"Step {step.id!r}: context_from entry missing 'step' field")
                if not ref.get("field"):
                    raise ValueError(f"Step {step.id!r}: context_from entry missing 'field' field")
                if ref_step not in seen_step_ids:
                    raise ValueError(
                        f"Step {step.id!r}: context_from references step {ref_step!r}"
                        f" which has not appeared before this step in execution order"
                    )

        seen_step_ids.add(step.id)


def validate_approval_mode(
    definition: WorkflowDefinition,
    effective_approval_mode: str,
) -> None:
    """Validate that workflow approval_mode is not more permissive than effective config.

    Strictness order: ask > ask_for_writes > ask_for_dangerous > auto
    A workflow can be equally strict or stricter, never more permissive.
    """
    strictness = {"auto": 0, "ask_for_dangerous": 1, "ask_for_writes": 2, "ask": 3}
    effective_level = strictness.get(effective_approval_mode, 2)

    for step in _all_steps(definition.steps):
        if step.approval_mode:
            step_level = strictness.get(step.approval_mode, -1)
            if step_level < 0:
                raise ValueError(f"Step {step.id!r}: invalid approval_mode {step.approval_mode!r}")
            if step_level < effective_level:
                raise ValueError(
                    f"Step {step.id!r}: approval_mode {step.approval_mode!r} is more permissive than"
                    f" effective config {effective_approval_mode!r}"
                )

    policy_mode = definition.policies.get("approval_mode")
    if policy_mode:
        policy_level = strictness.get(policy_mode, -1)
        if policy_level < 0:
            raise ValueError(f"Workflow policy approval_mode {policy_mode!r} is invalid")
        if policy_level < effective_level:
            raise ValueError(
                f"Workflow policy approval_mode {policy_mode!r} is more permissive than"
                f" effective config {effective_approval_mode!r}"
            )


def _all_steps(steps: list[WorkflowStepDef]) -> list[WorkflowStepDef]:
    """Flatten all steps including nested loop steps."""
    result: list[WorkflowStepDef] = []
    for step in steps:
        result.append(step)
        if step.steps:
            result.extend(_all_steps(step.steps))
    return result


# ---------------------------------------------------------------------------
# Engine (domain-neutral orchestrator)
# ---------------------------------------------------------------------------


class WorkflowEngine:
    """Executes workflow definitions. Domain-neutral.

    The engine knows about steps, runners, gates, and loops. It does not
    know about GitHub, issues, PRs, or any domain-specific concepts.
    """

    def __init__(
        self,
        db: ThreadSafeConnection,
        config: WorkflowConfig,
        runner_registry: RunnerRegistry,
        *,
        effective_approval_mode: str = "ask_for_writes",
        ai_service: Any | None = None,
        tool_executor: Any | None = None,
        tools_openai: list[dict[str, Any]] | None = None,
    ) -> None:
        self._db = db
        self._config = config
        self._runner_registry = runner_registry
        self._config_approval_mode = effective_approval_mode
        self._ai_service = ai_service
        self._tool_executor = tool_executor
        self._tools_openai = tools_openai

    async def start_run(
        self,
        definition: WorkflowDefinition,
        *,
        target_kind: str,
        target_ref: str,
        inputs: dict[str, Any] | None = None,
        space_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a new workflow run. Returns the run dict."""
        from . import workflow_storage as ws

        # Validate approval mode bounded by effective config
        effective_mode = self._config_approval_mode or "ask_for_writes"
        validate_approval_mode(definition, effective_mode)

        # Validate required inputs
        for name, schema in definition.inputs.items():
            if schema.get("required") and (not inputs or name not in inputs):
                raise ValueError(f"Missing required input: {name!r}")

        # Create run record
        run = ws.create_workflow_run(
            self._db,
            workflow_id=definition.id,
            workflow_version=definition.version,
            target_kind=target_kind,
            target_ref=target_ref,
            inputs=inputs,
            space_id=space_id,
        )

        # Acquire concurrency lock
        if not ws.acquire_lock(
            self._db,
            target_kind=target_kind,
            target_ref=target_ref,
            run_id=run["id"],
        ):
            ws.update_workflow_run(self._db, run["id"], status="failed", stop_reason="target_locked")
            raise RuntimeError(f"Target {target_kind}:{target_ref} is already locked by another run")

        # Mark running
        run = ws.update_workflow_run(
            self._db,
            run["id"],
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        ws.create_workflow_event(
            self._db, run_id=run["id"], event_type="run_started",
            payload={"workflow_id": definition.id, "target": f"{target_kind}:{target_ref}"},
        )

        try:
            run = await self._execute_steps(run, definition.steps, inputs or {}, definition)
        except Exception:
            logger.exception("Workflow run %s failed with exception", run["id"])
            run = ws.update_workflow_run(self._db, run["id"], status="failed", stop_reason="unhandled_exception")
            ws.create_workflow_event(
                self._db, run_id=run["id"], event_type="run_failed",
                payload={"reason": "exception"},
            )
        finally:
            ws.release_lock(self._db, run_id=run["id"])

        return run

    async def _execute_steps(
        self,
        run: dict[str, Any],
        steps: list[WorkflowStepDef],
        inputs: dict[str, Any],
        definition: WorkflowDefinition,
    ) -> dict[str, Any]:
        from . import workflow_storage as ws

        step_results: dict[str, dict[str, Any]] = {}

        for step_def in steps:
            step_record = ws.create_workflow_step(
                self._db,
                run_id=run["id"],
                step_id=step_def.id,
                step_type=step_def.type,
                runner_type=step_def.runner,
            )

            ws.update_workflow_run(self._db, run["id"], current_step_id=step_def.id)
            ws.create_workflow_event(
                self._db, run_id=run["id"], event_type="step_started",
                step_id=step_def.id, payload={"step_type": step_def.type},
            )

            start_time = time.monotonic()
            ws.update_workflow_step(
                self._db, step_record["id"],
                status="running",
                started_at=datetime.now(timezone.utc).isoformat(),
            )

            try:
                if step_def.type == "runner":
                    result = await self._execute_runner_step(step_def, run, inputs, step_results)
                elif step_def.type == "gate":
                    result = await self._execute_gate_step(step_def, run, inputs)
                elif step_def.type == "loop":
                    result = await self._execute_loop_step(step_def, run, inputs, definition, step_results)
                else:
                    raise ValueError(f"Unknown step type: {step_def.type!r}")
            except Exception as exc:
                duration_ms = int((time.monotonic() - start_time) * 1000)
                ws.update_workflow_step(
                    self._db, step_record["id"],
                    status="failed",
                    result_status="failed",
                    result_summary=str(exc),
                    duration_ms=duration_ms,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                ws.create_workflow_event(
                    self._db, run_id=run["id"], event_type="step_failed",
                    step_id=step_def.id, payload={"error": str(exc)},
                )
                run = ws.update_workflow_run(
                    self._db, run["id"],
                    status="failed",
                    stop_reason=f"step_failed:{step_def.id}",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                return run

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if result.status == "blocked":
                ws.update_workflow_step(
                    self._db, step_record["id"],
                    status="completed",
                    result_status="blocked",
                    result_summary=result.summary,
                    result_artifacts=result.artifacts,
                    duration_ms=duration_ms,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                ws.create_workflow_event(
                    self._db, run_id=run["id"], event_type="step_finished",
                    step_id=step_def.id, payload={"result_status": "blocked"},
                )
                run = ws.update_workflow_run(
                    self._db, run["id"],
                    status="blocked",
                    stop_reason=result.summary or f"blocked_at:{step_def.id}",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                return run

            ws.update_workflow_step(
                self._db, step_record["id"],
                status="completed",
                result_status=result.status,
                result_summary=result.summary,
                result_artifacts=result.artifacts,
                result_findings=result.findings,
                raw_output_path=result.raw_output_path,
                duration_ms=duration_ms,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            ws.create_workflow_event(
                self._db, run_id=run["id"], event_type="step_finished",
                step_id=step_def.id, payload={"result_status": result.status, "duration_ms": duration_ms},
            )

            step_results[step_def.id] = {
                "result_status": result.status,
                "result_summary": result.summary,
                "result_artifacts": result.artifacts,
                "result_findings": result.findings,
            }

            run = ws.update_workflow_run(
                self._db, run["id"],
                attempt_count=run.get("attempt_count", 0) + 1,
            )

        # All steps completed
        run = ws.update_workflow_run(
            self._db, run["id"],
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        ws.create_workflow_event(
            self._db, run_id=run["id"], event_type="run_completed",
            payload={"total_steps": len(steps)},
        )
        return run

    async def _execute_runner_step(
        self,
        step_def: WorkflowStepDef,
        run: dict[str, Any],
        inputs: dict[str, Any],
        step_results: dict[str, dict[str, Any]],
    ) -> RunnerResult:
        from .workflow_runners import execute_agent_runner, execute_opaque_runner

        if not step_def.runner:
            raise ValueError(f"Runner step {step_def.id!r} has no runner type")
        if not self._runner_registry.is_registered(step_def.runner):
            raise ValueError(f"Unknown runner type: {step_def.runner!r}")

        timeout = step_def.timeout or self._config.step_timeout

        # Resolve context from prior steps
        context = ""
        if step_def.context_from:
            context = resolve_context_from(step_def.context_from, step_results)

        if self._runner_registry.is_agent_runner(step_def.runner):
            prompt = step_def.prompt or ""
            if "{" in prompt:
                prompt = resolve_template(prompt, inputs)
            if context:
                prompt = f"{prompt}\n\n--- Prior step context ---\n{context}"
            return await execute_agent_runner(
                prompt=prompt,
                system_prompt=step_def.system_prompt,
                tools_filter=step_def.tools,
                timeout=timeout,
                ai_service=self._ai_service,
                tool_executor=self._tool_executor,
                tools_openai=self._tools_openai,
            )
        else:
            if step_def.runner == "shell":
                if not step_def.command:
                    raise ValueError(f"Shell runner step {step_def.id!r} has no command")
                command = resolve_template(step_def.command, inputs, shell_quote=True)
                return await execute_opaque_runner(
                    mode="shell",
                    command=command,
                    env=step_def.env,
                    working_dir=step_def.working_dir,
                    timeout=timeout,
                )
            elif step_def.runner == "python_script":
                if not step_def.command:
                    raise ValueError(f"Python script runner step {step_def.id!r} has no command")
                argv = [resolve_template(a, inputs) for a in (step_def.argv or [])]
                return await execute_opaque_runner(
                    mode="exec",
                    command=step_def.command,
                    argv=argv,
                    env=step_def.env,
                    working_dir=step_def.working_dir,
                    timeout=timeout,
                )
            else:
                raise ValueError(f"Unknown opaque runner: {step_def.runner!r}")

    async def _execute_gate_step(
        self,
        step_def: WorkflowStepDef,
        run: dict[str, Any],
        inputs: dict[str, Any],
    ) -> RunnerResult:
        from .workflow_runners import RunnerResult

        if not step_def.condition:
            raise ValueError(f"Gate step {step_def.id!r} has no condition")

        condition_fn = get_gate_condition(step_def.condition)
        if condition_fn is None:
            raise ValueError(f"Unknown gate condition: {step_def.condition!r}")

        passed = await condition_fn(run, step_def, inputs)

        if passed:
            return RunnerResult(status="success", summary=f"Gate {step_def.condition!r} passed")
        else:
            return RunnerResult(
                status="blocked",
                summary=step_def.if_false or f"Gate {step_def.condition!r} failed",
            )

    async def _execute_loop_step(
        self,
        step_def: WorkflowStepDef,
        run: dict[str, Any],
        inputs: dict[str, Any],
        definition: WorkflowDefinition,
        step_results: dict[str, dict[str, Any]],
    ) -> RunnerResult:
        from . import workflow_storage as ws
        from .workflow_runners import RunnerResult

        if not step_def.steps:
            return RunnerResult(status="success", summary="Empty loop")

        max_rounds = step_def.max_rounds or self._config.max_review_rounds
        rounds_completed = 0

        for round_num in range(1, max_rounds + 1):
            all_succeeded = True
            for nested_step in step_def.steps:
                # Persist nested step record (same durability as top-level steps)
                nested_step_id = f"{nested_step.id}_r{round_num}"
                nested_record = ws.create_workflow_step(
                    self._db,
                    run_id=run["id"],
                    step_id=nested_step_id,
                    step_type=nested_step.type,
                    runner_type=nested_step.runner,
                )
                ws.create_workflow_event(
                    self._db, run_id=run["id"], event_type="step_started",
                    step_id=nested_step_id,
                    payload={"step_type": nested_step.type, "loop": step_def.id, "round": round_num},
                )
                ws.update_workflow_step(
                    self._db, nested_record["id"],
                    status="running",
                    started_at=datetime.now(timezone.utc).isoformat(),
                )
                nested_start = time.monotonic()

                try:
                    if nested_step.type == "runner":
                        result = await self._execute_runner_step(nested_step, run, inputs, step_results)
                    elif nested_step.type == "gate":
                        result = await self._execute_gate_step(nested_step, run, inputs)
                    else:
                        raise ValueError(f"Unsupported step type in loop: {nested_step.type!r}")
                except Exception as exc:
                    nested_dur = int((time.monotonic() - nested_start) * 1000)
                    ws.update_workflow_step(
                        self._db, nested_record["id"],
                        status="failed", result_status="failed",
                        result_summary=str(exc), duration_ms=nested_dur,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    ws.create_workflow_event(
                        self._db, run_id=run["id"], event_type="step_failed",
                        step_id=nested_step_id, payload={"error": str(exc)},
                    )
                    return RunnerResult(status="failed", summary=f"Loop step {nested_step.id} failed: {exc}")

                # Persist nested step result
                nested_dur = int((time.monotonic() - nested_start) * 1000)
                ws.update_workflow_step(
                    self._db, nested_record["id"],
                    status="completed",
                    result_status=result.status,
                    result_summary=result.summary,
                    result_artifacts=result.artifacts,
                    result_findings=result.findings,
                    duration_ms=nested_dur,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                ws.create_workflow_event(
                    self._db, run_id=run["id"], event_type="step_finished",
                    step_id=nested_step_id,
                    payload={"result_status": result.status, "duration_ms": nested_dur},
                )

                step_results[nested_step.id] = {
                    "result_status": result.status,
                    "result_summary": result.summary,
                    "result_artifacts": result.artifacts,
                    "result_findings": result.findings,
                }

                if result.status != "success":
                    all_succeeded = False

            rounds_completed = round_num
            if all_succeeded:
                break

        return RunnerResult(
            status="success",
            summary=f"Loop completed after {rounds_completed}/{max_rounds} rounds",
        )
