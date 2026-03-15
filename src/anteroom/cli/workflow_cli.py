"""CLI subcommand handlers for `aroom workflow`.

Uses workflow-neutral language throughout. Domain-specific concepts
(issues, PRs) only appear in built-in workflow definitions, not here.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from ..config import AppConfig

logger = logging.getLogger(__name__)

console = Console()


def _resolve_workflow_path(workflow_id: str) -> Path | None:
    """Resolve a workflow definition by ID or path.

    Search order:
    1. Exact filesystem path (if it exists and ends in .yaml/.yml)
    2. examples/workflows/ directory (shipped reference workflows)
    3. src/anteroom/workflows/ directory (any future built-in generic workflows)
    """
    # Direct path
    candidate = Path(workflow_id)
    if candidate.exists() and candidate.suffix in (".yaml", ".yml"):
        return candidate

    # Reference workflows shipped with Anteroom
    examples_dir = Path(__file__).parent.parent.parent.parent / "examples" / "workflows"
    ref_path = examples_dir / f"{workflow_id}.yaml"
    if ref_path.exists():
        return ref_path

    # Built-in workflows (generic, shipped in package)
    builtin_dir = Path(__file__).parent.parent / "workflows"
    builtin_path = builtin_dir / f"{workflow_id}.yaml"
    if builtin_path.exists():
        return builtin_path

    return None


def _create_engine(config: AppConfig, db: Any) -> Any:
    """Create a WorkflowEngine with AI service dependencies wired in."""
    from ..services.workflow_engine import WorkflowEngine
    from ..services.workflow_runners import create_default_registry

    ai_service = None
    tool_executor = None
    tools_openai = None
    try:
        from ..services.ai_service import create_ai_service
        from ..tools import ToolRegistry, register_default_tools

        ai_service = create_ai_service(config.ai)
        tool_reg = ToolRegistry()
        register_default_tools(tool_reg, working_dir=str(Path.cwd()))
        tool_executor = tool_reg.call_tool
        tools_openai = tool_reg.get_openai_tools()
    except Exception as exc:
        logger.warning("Could not initialize AI service: %s", exc)
        console.print(
            "[yellow]Warning:[/yellow] AI service not available."
            " Agent runner steps will fail. Shell/script steps will work."
        )

    registry = create_default_registry()
    return WorkflowEngine(
        db,
        config.workflow,
        registry,
        effective_approval_mode=config.safety.approval_mode,
        ai_service=ai_service,
        tool_executor=tool_executor,
        tools_openai=tools_openai,
    )


def _run_workflow(config: AppConfig, args: argparse.Namespace) -> None:
    """Dispatch `aroom workflow` subcommands."""
    action = getattr(args, "workflow_action", None)
    if not action:
        console.print("Usage: aroom workflow {run,status,list,history,resume,cancel}")
        return

    from ..db import get_db

    db = get_db(config.app.data_dir / "chat.db")

    if action == "run":
        _handle_run(config, db, args)
    elif action == "status":
        _handle_status(db, args)
    elif action == "list":
        _handle_list(config, db, args)
    elif action == "history":
        _handle_history(db, args)
    elif action == "resume":
        _handle_resume(config, db, args)
    elif action == "cancel":
        _handle_cancel(db, args)
    else:
        console.print(f"Unknown workflow action: {action}")


def _handle_run(config: AppConfig, db: Any, args: argparse.Namespace) -> None:
    """Handle `aroom workflow run <workflow_id>`."""
    from ..services.workflow_engine import load_definition

    workflow_id = getattr(args, "workflow_name", None)
    if not workflow_id:
        console.print("[red]Error:[/red] workflow name is required")
        return

    # Resolve definition: filesystem path, reference example, or built-in
    path = _resolve_workflow_path(workflow_id)
    if path is None:
        console.print(f"[red]Error:[/red] Workflow not found: {workflow_id!r}")
        console.print("Provide a path to a YAML workflow definition.")
        return

    try:
        definition = load_definition(path)
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]Error loading workflow:[/red] {exc}")
        return

    # Collect inputs from CLI args
    inputs: dict[str, Any] = {}
    issue_number = getattr(args, "issue", None)
    if issue_number is not None:
        inputs["issue_number"] = issue_number

    # Determine target from inputs or definition
    target_kind = "workflow"
    target_ref = workflow_id
    if "issue_number" in inputs:
        target_kind = "issue"
        target_ref = str(inputs["issue_number"])

    # Dry run: show plan without executing
    if getattr(args, "dry_run", False):
        console.print(f"\n[bold]Workflow:[/bold] {definition.id} v{definition.version}")
        console.print(f"[bold]Target:[/bold] {target_kind}:{target_ref}")
        console.print(f"[bold]Inputs:[/bold] {inputs}")
        console.print(f"\n[bold]Steps ({len(definition.steps)}):[/bold]")
        for i, step in enumerate(definition.steps, 1):
            label = f"  {i}. [{step.type}] {step.id}"
            if step.runner:
                label += f" ({step.runner})"
            console.print(label)
        return

    # Register gate conditions for reference workflows (e.g., issue_delivery).
    # These are GitHub-specific gates — they live in workflows/gates.py,
    # not in the engine core.
    from ..workflows.gates import register_builtin_gates

    register_builtin_gates()

    # Create engine with AI service dependencies
    engine = _create_engine(config, db)

    # Execute
    console.print(f"\n[bold]Starting workflow:[/bold] {definition.id} v{definition.version}")
    console.print(f"[bold]Target:[/bold] {target_kind}:{target_ref}\n")

    try:
        run = asyncio.run(engine.start_run(
            definition,
            target_kind=target_kind,
            target_ref=target_ref,
            inputs=inputs,
        ))
    except (ValueError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return

    # Report result
    status = run.get("status", "unknown")
    if status == "completed":
        console.print("\n[green]Workflow completed successfully[/green]")
    elif status == "blocked":
        console.print(f"\n[yellow]Workflow blocked:[/yellow] {run.get('stop_reason', 'unknown')}")
    elif status == "failed":
        console.print(f"\n[red]Workflow failed:[/red] {run.get('stop_reason', 'unknown')}")
    else:
        console.print(f"\n[dim]Workflow status:[/dim] {status}")

    console.print(f"[dim]Run ID:[/dim] {run['id']}")


def _handle_status(db: Any, args: argparse.Namespace) -> None:
    """Handle `aroom workflow status <run_id>`."""
    from ..services.workflow_storage import get_workflow_run, list_workflow_steps

    run_id = getattr(args, "run_id", None)
    if not run_id:
        console.print("[red]Error:[/red] run_id is required")
        return

    run = get_workflow_run(db, run_id)
    if not run:
        console.print(f"[red]Error:[/red] Run not found: {run_id}")
        return

    console.print(f"\n[bold]Run:[/bold] {run['id'][:12]}...")
    console.print(f"[bold]Workflow:[/bold] {run['workflow_id']} v{run.get('workflow_version', '?')}")
    console.print(f"[bold]Target:[/bold] {run['target_kind']}:{run['target_ref']}")
    console.print(f"[bold]Status:[/bold] {run['status']}")
    if run.get("stop_reason"):
        console.print(f"[bold]Stop reason:[/bold] {run['stop_reason']}")
    if run.get("current_step_id"):
        console.print(f"[bold]Current step:[/bold] {run['current_step_id']}")
    console.print(f"[bold]Created:[/bold] {run['created_at']}")

    steps = list_workflow_steps(db, run["id"])
    if steps:
        console.print(f"\n[bold]Steps ({len(steps)}):[/bold]")
        table = Table(show_header=True)
        table.add_column("Step", style="bold")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Summary", max_width=60)
        for step in steps:
            dur = f"{step['duration_ms']}ms" if step.get("duration_ms") else "-"
            table.add_row(
                step["step_id"],
                step["step_type"],
                step["status"],
                dur,
                (step.get("result_summary") or "")[:60],
            )
        console.print(table)


def _handle_list(config: AppConfig, db: Any, args: argparse.Namespace) -> None:
    """Handle `aroom workflow list`."""
    from ..services.workflow_storage import list_workflow_runs

    # Recover stale runs before listing (on-demand recovery)
    engine = _create_engine(config, db)
    recovered = asyncio.run(engine.recover_interrupted_runs())
    if recovered:
        console.print(f"[yellow]Recovered {len(recovered)} interrupted run(s)[/yellow]")

    status_filter = getattr(args, "status", None)
    workflow_filter = getattr(args, "workflow", None)
    limit = getattr(args, "limit", 20) or 20

    runs = list_workflow_runs(db, status=status_filter, workflow_id=workflow_filter, limit=limit)

    if not runs:
        console.print("[dim]No workflow runs found.[/dim]")
        return

    table = Table(title="Workflow Runs", show_header=True)
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Workflow")
    table.add_column("Target")
    table.add_column("Status")
    table.add_column("Step")
    table.add_column("Created")

    for run in runs:
        table.add_row(
            run["id"][:12],
            run["workflow_id"],
            f"{run['target_kind']}:{run['target_ref']}",
            run["status"],
            run.get("current_step_id") or "-",
            run["created_at"][:19],
        )

    console.print(table)


def _handle_history(db: Any, args: argparse.Namespace) -> None:
    """Handle `aroom workflow history <run_id>`."""
    from ..services.workflow_storage import get_workflow_run, list_workflow_events, list_workflow_steps

    run_id = getattr(args, "run_id", None)
    if not run_id:
        console.print("[red]Error:[/red] run_id is required")
        return

    run = get_workflow_run(db, run_id)
    if not run:
        console.print(f"[red]Error:[/red] Run not found: {run_id}")
        return

    console.print(f"\n[bold]Run History:[/bold] {run['id'][:12]}...")
    console.print(f"[bold]Workflow:[/bold] {run['workflow_id']} — Status: {run['status']}")

    steps = list_workflow_steps(db, run["id"])
    if steps:
        console.print("\n[bold]Steps:[/bold]")
        table = Table(show_header=True)
        table.add_column("Step", style="bold")
        table.add_column("Type")
        table.add_column("Runner")
        table.add_column("Status")
        table.add_column("Result")
        table.add_column("Duration")
        table.add_column("Summary", max_width=50)
        for step in steps:
            dur = f"{step['duration_ms']}ms" if step.get("duration_ms") else "-"
            table.add_row(
                step["step_id"],
                step["step_type"],
                step.get("runner_type") or "-",
                step["status"],
                step.get("result_status") or "-",
                dur,
                (step.get("result_summary") or "")[:50],
            )
        console.print(table)

    events = list_workflow_events(db, run["id"])
    if events:
        console.print(f"\n[bold]Events ({len(events)}):[/bold]")
        table = Table(show_header=True)
        table.add_column("ID", style="dim")
        table.add_column("Type")
        table.add_column("Step")
        table.add_column("Time")
        for event in events:
            table.add_row(
                str(event["id"]),
                event["event_type"],
                event.get("step_id") or "-",
                event["created_at"][:19],
            )
        console.print(table)


def _handle_resume(config: AppConfig, db: Any, args: argparse.Namespace) -> None:
    """Handle `aroom workflow resume <run_id>`."""
    from ..services.workflow_engine import load_definition
    from ..services.workflow_storage import get_workflow_run

    run_id = getattr(args, "run_id", None)
    if not run_id:
        console.print("[red]Error:[/red] run_id is required")
        return

    # Create engine with full AI/tool wiring (same as _handle_run)
    engine = _create_engine(config, db)

    # Recover any stale runs first (on-demand recovery)
    asyncio.run(engine.recover_interrupted_runs())

    run = get_workflow_run(db, run_id)
    if not run:
        console.print(f"[red]Error:[/red] Run not found: {run_id}")
        return

    if run["status"] not in ("paused", "waiting_for_approval"):
        console.print(
            f"[red]Error:[/red] Run is not resumable (status: {run['status']}). "
            "Only paused or waiting_for_approval runs can be resumed."
        )
        return

    # Resolve definition
    definition_path = getattr(args, "definition", None)
    workflow_id = run.get("workflow_id", "")

    if definition_path:
        path = Path(definition_path)
    else:
        path = _resolve_workflow_path(workflow_id)

    if not path:
        console.print(
            f"[red]Error:[/red] Cannot find workflow definition for '{workflow_id}'. "
            "Pass --definition <path> for custom workflows."
        )
        return

    try:
        definition = load_definition(path)
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]Error loading workflow:[/red] {exc}")
        return

    from_step = getattr(args, "from_step", None)

    # Register gates
    from ..workflows.gates import register_builtin_gates

    register_builtin_gates()

    console.print(f"\n[bold]Resuming workflow:[/bold] {definition.id}")
    console.print(f"[bold]Run:[/bold] {run_id[:12]}...")
    if from_step:
        console.print(f"[bold]From step:[/bold] {from_step}")

    try:
        result = asyncio.run(engine.resume_run(
            run_id, definition, from_step=from_step,
        ))
    except (ValueError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return

    status = result.get("status", "unknown")
    if status == "completed":
        console.print("\n[green]Workflow completed successfully[/green]")
    elif status == "blocked":
        console.print(f"\n[yellow]Workflow blocked:[/yellow] {result.get('stop_reason', 'unknown')}")
    elif status == "failed":
        console.print(f"\n[red]Workflow failed:[/red] {result.get('stop_reason', 'unknown')}")
    else:
        console.print(f"\n[dim]Workflow status:[/dim] {status}")


def _handle_cancel(db: Any, args: argparse.Namespace) -> None:
    """Handle `aroom workflow cancel <run_id>`. Paused runs only in V1."""
    from ..services.workflow_storage import (
        create_workflow_event,
        get_workflow_run,
        release_lock,
        update_workflow_run,
    )

    run_id = getattr(args, "run_id", None)
    if not run_id:
        console.print("[red]Error:[/red] run_id is required")
        return

    run = get_workflow_run(db, run_id)
    if not run:
        console.print(f"[red]Error:[/red] Run not found: {run_id}")
        return

    if run["status"] == "running":
        console.print(
            "[red]Error:[/red] Cannot cancel an active run from another terminal. "
            "Use Ctrl-C in the terminal running the workflow."
        )
        return

    if run["status"] not in ("paused", "waiting_for_approval"):
        console.print(
            f"[red]Error:[/red] Run is not cancellable (status: {run['status']}). "
            "Only paused or waiting_for_approval runs can be cancelled."
        )
        return

    update_workflow_run(db, run_id, status="cancelled")
    release_lock(db, run_id=run_id)
    create_workflow_event(
        db, run_id=run_id, event_type="run_cancelled",
        payload={"cancelled_from_status": run["status"]},
    )
    console.print(f"[green]Run {run_id[:12]}... cancelled[/green]")
