"""tycoon ai — local LLM pipeline assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tycoon.ai.client import chat, get_status
from tycoon.ai.context import gather_context
from tycoon.ai.file_proposals import parse_proposals
from tycoon.ai.prompts import build_system_prompt
from tycoon.ai.repl import run_repl
from tycoon.config import config
from tycoon.utils.console import console, error, header, info, status_table, success, warn

app = typer.Typer(help="Local LLM pipeline assistant (LM Studio).")


def _ensure_ready() -> None:
    """Check that LM Studio is running with a loaded model, or exit."""
    st = get_status()
    if not st.running:
        error("LM Studio server is not running.")
        info("Start the local server in LM Studio (Developer tab)")
        raise typer.Exit(1)
    if not st.loaded_models:
        error("No model loaded in LM Studio.")
        info("Load a model in LM Studio to get started")
        raise typer.Exit(1)


def _gather_project_context() -> str:
    """Build the system prompt from the current project context."""
    project = config.project
    ctx = gather_context(
        project_root=config.root,
        raw_db=config.raw_db,
        warehouse_db=config.local_db,
        dbt_dir=config.dbt_project_dir,
        sources=config.sources or None,
        project_name=project.name if project else "",
    )
    return build_system_prompt(ctx)


def _confirm_proposal(path: str, content: str) -> bool | str:
    """Show a file proposal and ask for confirmation.

    Returns True to write, False to skip, or 'edit' if user wants to edit.
    """
    console.print(f"\n[bold cyan]Proposed file:[/bold cyan] {path}")
    console.print("─" * 60)
    for i, line in enumerate(content.splitlines(), 1):
        console.print(f"[dim]{i:3d}[/dim] {line}")
    console.print("─" * 60)

    choice = typer.prompt("Write this file? [y]es / [n]o / [e]dit", default="y")
    choice = choice.strip().lower()
    if choice in ("y", "yes"):
        return True
    if choice in ("e", "edit"):
        return "edit"
    return False


@app.command()
def status() -> None:
    """Check LM Studio server and model availability."""
    header("Tycoon AI Status")

    st = get_status()
    rows: list[tuple[str, str, str]] = []

    if st.running:
        rows.append(("LM Studio server", "OK", "running on localhost:1234"))
    else:
        rows.append(("LM Studio server", "FAIL", "not running — start the local server in LM Studio"))

    if st.models:
        rows.append(("Available models", "OK", f"{len(st.models)} model(s)"))
        for m in st.models:
            label = "loaded" if m.loaded else "not loaded"
            detail = f"{label}"
            if m.quantization:
                detail += f" | {m.quantization}"
            if m.max_context_length:
                detail += f" | {m.max_context_length:,} ctx"
            rows.append((f"  {m.id}", "OK" if m.loaded else "WARN", detail))
    else:
        rows.append(("Available models", "WARN", "no models found — download one in LM Studio"))

    loaded = st.loaded_models
    if loaded:
        rows.append(("Active model", "OK", loaded[0].id))
    elif st.running:
        rows.append(("Active model", "WARN", "no model loaded — load one in LM Studio"))

    console.print(status_table(rows, title="AI Status"))

    if st.ready:
        success("AI assistant is ready")
    else:
        warn("AI assistant is not fully configured")
        if not st.running:
            info("Start the local server in LM Studio (Developer tab)")
        elif not loaded:
            info("Load a model in LM Studio to get started")


@app.command()
def setup() -> None:
    """Verify LM Studio is running and a model is loaded."""
    header("Tycoon AI Setup")

    st = get_status()

    if not st.running:
        error("LM Studio server is not running.")
        info("Open LM Studio and start the local server (Developer tab)")
        info("The server should be available at [bold]http://localhost:1234[/bold]")
        raise typer.Exit(1)
    success("LM Studio server is running")

    loaded = st.loaded_models
    if not loaded:
        error("No model is loaded.")
        info("Load a model in LM Studio — any chat model will work")
        info("Recommended: Qwen 2.5 Coder 7B or similar")
        raise typer.Exit(1)
    success(f"Model loaded: [bold]{loaded[0].id}[/bold]")

    success("AI assistant is ready! Try: [bold]tycoon ai status[/bold]")


@app.command(name="ask")
def ask_cmd(
    prompt: Annotated[str, typer.Argument(help="What to ask the AI assistant.")],
    model: Annotated[str | None, typer.Option("--model", "-m", help="Override the model to use.")] = None,
    no_context: Annotated[bool, typer.Option("--no-context", help="Skip project context gathering.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show the prompt without sending it.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Auto-accept all file proposals.")] = False,
) -> None:
    """Ask the AI assistant a question about your pipeline.

    The assistant sees your project context (schemas, dbt models, sources)
    and can propose file changes.

    Examples:
        tycoon ai ask "write a staging model for the events table"
        tycoon ai ask "why is the not_null test failing on trips?"
        tycoon ai ask "add a dlt source for the GitHub API"
    """
    if not dry_run:
        _ensure_ready()

    # Build context
    if no_context:
        system_prompt = (
            "You are a data pipeline assistant. The stack uses: "
            "dlt (ingestion) → DuckDB (storage) → dbt (transforms). "
            "When proposing file changes, use fenced code blocks with the "
            "target file path as the language identifier."
        )
    else:
        info("Gathering project context...")
        system_prompt = _gather_project_context()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    if dry_run:
        console.print("\n[bold]System prompt:[/bold]")
        console.print(system_prompt)
        console.print(f"\n[bold]User prompt:[/bold] {prompt}")
        console.print(f"\n[dim]Total system prompt length: {len(system_prompt):,} chars[/dim]")
        return

    # Call LM Studio
    info("Thinking...")
    try:
        response = chat(messages, model=model)
    except Exception as exc:
        error(f"LM Studio request failed: {exc}")
        raise typer.Exit(1) from exc

    # Display response
    console.print()
    console.print(response)

    # Handle file proposals
    proposals = parse_proposals(response)
    if proposals:
        console.print(f"\n[bold]{len(proposals)} file proposal(s) detected[/bold]")
        written = 0
        for proposal in proposals:
            if yes:
                accept = True
            else:
                accept = _confirm_proposal(proposal.path, proposal.content)

            if accept is True:
                target = Path(proposal.path)
                if not target.is_absolute():
                    target = config.root / target
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(proposal.content)
                success(f"Wrote {proposal.path}")
                written += 1
            elif accept == "edit":
                info(f"Skipped {proposal.path} (edit not yet implemented)")
            else:
                info(f"Skipped {proposal.path}")

        if written:
            success(f"{written} file(s) written")


@app.command(name="chat")
def chat_cmd(
    model: Annotated[str | None, typer.Option("--model", "-m", help="Override the model to use.")] = None,
    no_context: Annotated[bool, typer.Option("--no-context", help="Skip project context gathering.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Auto-accept all file proposals.")] = False,
) -> None:
    """Start an interactive chat session with the AI assistant.

    The assistant has full project context and can propose file changes
    across multiple turns. Use /help inside the chat for commands.
    """
    _ensure_ready()

    if no_context:
        system_prompt = (
            "You are a data pipeline assistant. The stack uses: "
            "dlt (ingestion) → DuckDB (storage) → dbt (transforms). "
            "When proposing file changes, use fenced code blocks with the "
            "target file path as the language identifier."
        )
    else:
        info("Gathering project context...")
        system_prompt = _gather_project_context()

    run_repl(
        system_prompt=system_prompt,
        project_root=config.root,
        model=model,
        auto_accept=yes,
    )
