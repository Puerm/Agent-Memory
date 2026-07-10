"""Terminal interface for the complete memory strategy demonstration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agent import DemoAgent
from .environment import DemoProjectEnvironment
from .events import EventStore
from .memory import GovernedMemory, NaiveMemory, NoneMemory
from .memory.base import MemorySystem
from .memory.store import MemoryStore
from .metrics import MetricsCollector
from .scenarios import build_learning_task, inject_unsafe_memory

app = typer.Typer(help="Deterministic Agent Memory experiment lab.", no_args_is_help=True)
memory_app = typer.Typer(help="Inspect stored memory cards and admission decisions.", no_args_is_help=True)
app.add_typer(memory_app, name="memory")
console = Console()


def data_dir() -> Path:
    configured = os.environ.get("MEMORY_LAB_DATA", "data")
    return Path(configured).expanduser().resolve()


def store() -> MemoryStore:
    return MemoryStore(data_dir() / "memory.db")


def event_store() -> EventStore:
    return EventStore(data_dir() / "events.jsonl")


def metrics() -> MetricsCollector:
    return MetricsCollector(data_dir() / "metrics.jsonl")


def memory_system(mode: str, memory_store: MemoryStore) -> MemorySystem:
    if mode == "none":
        return NoneMemory()
    if mode == "naive":
        return NaiveMemory(memory_store)
    if mode == "governed":
        return GovernedMemory(memory_store)
    raise typer.BadParameter("mode must be one of: none, naive, governed")


def render_decisions(decisions: list) -> None:
    if not decisions:
        return
    table = Table(title="Memory admission / retrieval decisions")
    table.add_column("MEMORY")
    table.add_column("SIMILARITY", justify="right")
    table.add_column("ADMITTED")
    table.add_column("FINAL", justify="right")
    table.add_column("REASONS")
    for decision in decisions:
        table.add_row(
            decision.memory_id,
            f"{decision.semantic_score:.2f}",
            "YES" if decision.admitted else "NO",
            "-" if decision.final_score is None else f"{decision.final_score:.2f}",
            ", ".join(decision.reason_codes),
        )
    console.print(table)


@app.command()
def reset() -> None:
    """Clear local experiment data while leaving source code untouched."""
    memory_store = store()
    memory_store.clear()
    for file_name in ("events.jsonl", "metrics.jsonl"):
        target = data_dir() / file_name
        if target.exists():
            target.unlink()
    console.print(f"[green]Experiment state cleared:[/] {data_dir()}")


@app.command()
def run(
    scenario: Annotated[str, typer.Argument(help="learn-1, learn-2, or injection")],
    mode: Annotated[str, typer.Option(help="none, naive, or governed")] = "governed",
) -> None:
    """Run one fresh-session scenario and retain only the selected memory policy's state."""
    try:
        task = build_learning_task(scenario)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    memory_store = store()
    memory = memory_system(mode, memory_store)
    agent = DemoAgent(DemoProjectEnvironment(), event_store())
    result = agent.run_task(task, memory, scenario)
    metrics().append(result)

    summary = Table(title=f"Run: {scenario} ({mode})")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Session", result.session_id)
    summary.add_row("Success", "YES" if result.success else "NO")
    summary.add_row("Tool calls", str(result.tool_calls))
    summary.add_row("Failed tool calls", str(result.failed_tool_calls))
    summary.add_row("Errors", ", ".join(result.errors) or "none")
    summary.add_row("Admitted memory", ", ".join(result.admitted_memory_ids) or "none")
    summary.add_row("Memory tokens (estimate)", str(result.estimated_memory_tokens))
    summary.add_row("Elapsed", f"{result.elapsed_ms:.2f} ms")
    console.print(summary)
    render_decisions(result.decisions)


@app.command("inject")
def inject(target: Annotated[str, typer.Argument(help="Currently supports unsafe-memory")]) -> None:
    """Insert the unsafe-memory fixture for the retrieval-admission demonstration."""
    if target != "unsafe-memory":
        raise typer.BadParameter("Only unsafe-memory is supported")
    card = inject_unsafe_memory(store())
    console.print(
        Panel(
            f"Inserted [bold]{card.memory_id}[/bold] as an untrusted, high-risk memory scoped to "
            f"[bold]{card.project_id}[/bold].\nIt is also present in the raw NaiveMemory corpus.",
            title="Unsafe memory injected",
        )
    )


@app.command()
def report() -> None:
    """Show the latest observed metrics for each scenario and memory strategy."""
    rows = metrics().all()
    if not rows:
        console.print("No run metrics yet. Run a scenario first.")
        return
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        latest[(row["scenario"], row["mode"])] = row
    table = Table(title="Latest experiment metrics")
    for column in ("SCENARIO", "MODE", "SUCCESS", "TOOLS", "FAILURES", "MEMORY TOKENS", "ERRORS"):
        table.add_column(column, justify="right" if column in {"TOOLS", "FAILURES", "MEMORY TOKENS"} else "left")
    for (scenario, mode), row in sorted(latest.items()):
        table.add_row(
            scenario,
            mode,
            "YES" if row["success"] else "NO",
            str(row["tool_calls"]),
            str(row["failed_tool_calls"]),
            str(row["estimated_memory_tokens"]),
            ", ".join(row.get("errors", [])) or "none",
        )
    console.print(table)


@memory_app.command("list")
def list_memory() -> None:
    """List structured cards; raw NaiveMemory records are intentionally not cards."""
    cards = store().list_cards()
    if not cards:
        console.print("No structured memory cards stored.")
        return
    table = Table(title="Structured Memory Cards")
    for column in ("ID", "TYPE", "PROJECT", "TRUST", "RISK", "STATUS", "USES"):
        table.add_column(column)
    for card in cards:
        table.add_row(
            card.memory_id,
            card.memory_type,
            card.project_id or "global",
            card.trust_level,
            card.risk_level,
            card.status,
            str(card.use_count),
        )
    console.print(table)


@memory_app.command("show")
def show_memory(memory_id: str) -> None:
    """Render one complete structured Memory Card."""
    card = store().get_card(memory_id)
    if card is None:
        raise typer.BadParameter(f"Unknown memory id: {memory_id}")
    console.print(Panel(card.model_dump_json(indent=2), title=f"Memory Card: {memory_id}"))


@memory_app.command("explain")
def explain(
    scenario: Annotated[str, typer.Option(help="learn-1, learn-2, or injection")] = "injection",
    mode: Annotated[str, typer.Option(help="none, naive, or governed")] = "governed",
) -> None:
    """Re-run retrieval only and expose every admission decision before prompt assembly."""
    try:
        task = build_learning_task(scenario)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    retrieval = memory_system(mode, store()).query(task)
    console.print(f"Task: [bold]{task.task_text}[/bold]")
    render_decisions(retrieval.decisions)
    if mode == "governed":
        admitted = ", ".join(card.memory_id for card in retrieval.cards) or "none"
        console.print(f"Prompt assembly receives: [green]{admitted}[/green]")


def main() -> None:
    app()
