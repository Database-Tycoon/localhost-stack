"""tycoon ai — local LLM pipeline assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tycoon.ai.client import chat, get_status
from tycoon.ai.context import gather_context
from tycoon.ai.file_proposals import parse_proposals
from tycoon.ai.fix_loop import run_fix_loop
from tycoon.ai.memory import append_memory, get_memory_path, read_memory, write_memory
from tycoon.ai.prompts import build_system_prompt
from tycoon.ai.repl import run_repl
from tycoon.config import config
from tycoon.utils.console import ai_hint, console, error, header, info, status_table, success, warn

app = typer.Typer(help="Local LLM pipeline assistant (LM Studio).")

memory_app = typer.Typer(help="Manage project AI memory.")
app.add_typer(memory_app, name="memory")


@memory_app.command(name="show")
def memory_show() -> None:
    """Print the current project AI memory contents."""
    content = read_memory(config.root)
    if not content:
        info("No AI memory file found. Use 'tycoon ai memory add' to create one.")
        return
    console.print(content)


@memory_app.command(name="add")
def memory_add(
    note: Annotated[str, typer.Argument(help="Note or decision to add to project memory.")],
) -> None:
    """Append a note directly to the project AI memory."""
    append_memory(config.root, note)
    success(f"Added to AI memory: {note}")


@memory_app.command(name="clear")
def memory_clear(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
) -> None:
    """Clear all project AI memory (requires confirmation)."""
    path = get_memory_path(config.root)
    if not path.exists():
        info("No AI memory file found — nothing to clear.")
        return
    if not yes:
        confirmed = typer.confirm("Clear all AI memory? This cannot be undone.")
        if not confirmed:
            info("Aborted.")
            return
    write_memory(config.root, "")
    success("AI memory cleared.")


@memory_app.command(name="path")
def memory_path_cmd() -> None:
    """Print the path to the AI memory file."""
    console.print(str(get_memory_path(config.root)))


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


@app.command()
def fix(
    model: Annotated[str | None, typer.Option("--model", "-m", help="Override the model to use.")] = None,
    max_attempts: Annotated[int, typer.Option("--max-attempts", help="Max fix attempts.")] = 3,
    target: Annotated[str, typer.Option("--target", "-t", help="dbt target profile (default: local).")] = "local",
    select: Annotated[str | None, typer.Option("--select", "-s", help="dbt model selection syntax.")] = None,
) -> None:
    """Automatically fix failing dbt tests using the AI assistant.

    Runs dbt tests, feeds failures to the AI, applies proposed fixes,
    and repeats until all tests pass or the attempt limit is reached.

    Examples:
        tycoon ai fix
        tycoon ai fix --max-attempts 5
        tycoon ai fix --select staging --target dev
    """
    _ensure_ready()

    header("Tycoon AI Fix")

    passed = run_fix_loop(
        dbt_dir=config.dbt_project_dir,
        project_root=config.root,
        model=model,
        max_attempts=max_attempts,
        target=target,
        select=select,
    )

    if passed:
        success("All dbt tests are passing.")
    else:
        error("Could not fix all dbt test failures automatically.")
        ai_hint("what else could be causing my dbt test failures?")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Named pipeline registry
# ---------------------------------------------------------------------------

_AVAILABLE_PIPELINES: list[str] = [
    "document-staging",
    "fix-nulls",
    "review-staging",
    "debug-pipeline",
    "drift-check",
]


def _build_document_staging_pipeline(
    model_name: str,
    profile_summary: str,
    model_path: str,
    project_root: Path,
    dry_run: bool,
) -> tuple[object, dict]:
    """Construct the document-staging WorkerPipeline and initial_inputs dict."""
    from tycoon.ai.workers.base import WorkerPipeline
    from tycoon.ai.workers.staging import ColumnDocumenter
    from tycoon.ai.workers.tests import TestWriter

    steps = [
        (
            ColumnDocumenter(),
            {
                "model_name": "model_name",
                "profile_summary": "profile_summary",
                "existing_schema_yaml": "existing_schema_yaml",
            },
        ),
        (
            TestWriter(),
            {
                "model_name": "model_name",
                "model_path": "model_path",
                "profile_summary": "profile_summary",
            },
        ),
    ]

    pipeline = WorkerPipeline(steps=steps, project_root=project_root, dry_run=dry_run)

    initial_inputs = {
        "model_name": model_name,
        "profile_summary": profile_summary,
        "model_path": model_path,
        "existing_schema_yaml": "",
    }

    return pipeline, initial_inputs


def _build_fix_nulls_pipeline(
    model_name: str,
    profile_summary: str,
    model_sql: str,
    model_path: str,
    project_root: Path,
    dry_run: bool,
) -> tuple[object, dict]:
    """Construct the fix-nulls WorkerPipeline and initial_inputs dict."""
    from tycoon.ai.workers.base import WorkerPipeline
    from tycoon.ai.workers.staging import NullHandler
    from tycoon.ai.workers.tests import TestWriter

    steps = [
        (
            NullHandler(),
            {
                "model_name": "model_name",
                "model_sql": "model_sql",
                "profile_summary": "profile_summary",
            },
        ),
        (
            TestWriter(),
            {
                "model_name": "model_name",
                "model_path": "model_path",
                "profile_summary": "profile_summary",
            },
        ),
    ]

    pipeline = WorkerPipeline(steps=steps, project_root=project_root, dry_run=dry_run)
    initial_inputs = {
        "model_name": model_name,
        "profile_summary": profile_summary,
        "model_sql": model_sql,
        "model_path": model_path,
    }
    return pipeline, initial_inputs


def _build_review_staging_pipeline(
    model_name: str,
    profile_summary: str,
    model_sql: str,
    model_path: str,
    project_root: Path,
    dry_run: bool,
) -> tuple[object, dict]:
    """Construct the review-staging WorkerPipeline and initial_inputs dict."""
    from tycoon.ai.workers.base import WorkerPipeline
    from tycoon.ai.workers.staging import StagingImprover, ColumnRenamer, ColumnDocumenter

    steps = [
        (
            StagingImprover(),
            {
                "model_name": "model_name",
                "model_sql": "model_sql",
                "profile_summary": "profile_summary",
            },
        ),
        (
            ColumnRenamer(),
            {
                "model_name": "model_name",
                "model_sql": "model_sql",
                "profile_summary": "profile_summary",
            },
        ),
        (
            ColumnDocumenter(),
            {
                "model_name": "model_name",
                "profile_summary": "profile_summary",
                "existing_schema_yaml": "existing_schema_yaml",
            },
        ),
    ]

    pipeline = WorkerPipeline(steps=steps, project_root=project_root, dry_run=dry_run)
    initial_inputs = {
        "model_name": model_name,
        "profile_summary": profile_summary,
        "model_sql": model_sql,
        "model_path": model_path,
        "existing_schema_yaml": "",
    }
    return pipeline, initial_inputs


def _build_debug_pipeline_pipeline(
    pipeline_name: str,
    error_output: str,
    source_config: str,
    project_root: Path,
    dry_run: bool,
) -> tuple[object, dict]:
    """Construct the debug-pipeline WorkerPipeline and initial_inputs dict."""
    from tycoon.ai.workers.base import WorkerPipeline
    from tycoon.ai.workers.ingestion import PipelineDebugger

    steps = [
        (
            PipelineDebugger(),
            {
                "pipeline_name": "pipeline_name",
                "error_output": "error_output",
                "source_config": "source_config",
            },
        ),
    ]

    pipeline = WorkerPipeline(steps=steps, project_root=project_root, dry_run=dry_run)
    initial_inputs = {
        "pipeline_name": pipeline_name,
        "error_output": error_output,
        "source_config": source_config,
    }
    return pipeline, initial_inputs


def _build_drift_check_pipeline(
    expected_schema: str,
    actual_schema: str,
    source_name: str,
    project_root: Path,
    dry_run: bool,
) -> tuple[object, dict]:
    """Construct the drift-check WorkerPipeline and initial_inputs dict."""
    from tycoon.ai.workers.base import WorkerPipeline
    from tycoon.ai.workers.ingestion import SchemaDriftDetector

    steps = [
        (
            SchemaDriftDetector(),
            {
                "source_name": "source_name",
                "expected_schema": "expected_schema",
                "actual_schema": "actual_schema",
            },
        ),
    ]

    pipeline = WorkerPipeline(steps=steps, project_root=project_root, dry_run=dry_run)
    initial_inputs = {
        "source_name": source_name,
        "expected_schema": expected_schema,
        "actual_schema": actual_schema,
    }
    return pipeline, initial_inputs


@app.command(name="pipeline")
def pipeline_cmd(
    name: Annotated[str, typer.Argument(help="Pipeline name (e.g. document-staging).")],
    model: Annotated[str, typer.Option("--model", "-m", help="dbt model name (or subject name for debug-pipeline / drift-check).")],
    db_path: Annotated[
        str | None,
        typer.Option("--db", help="Path to DuckDB file. Defaults to config raw_db. For debug-pipeline pass the error log path; for drift-check pass expected schema path."),
    ] = None,
    schema: Annotated[str, typer.Option("--schema", help="DuckDB schema name.")] = "main",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Parse proposals but do not write files."),
    ] = False,
) -> None:
    """Run a named AI worker pipeline against a dbt model.

    Available pipelines:
        document-staging  — ColumnDocumenter → TestWriter
        fix-nulls         — NullHandler → TestWriter
        review-staging    — StagingImprover → ColumnRenamer → ColumnDocumenter
        debug-pipeline    — PipelineDebugger (standalone; --model is the pipeline name,
                            --db is the path to an error log file)
        drift-check       — SchemaDriftDetector (standalone; --model is the source name,
                            --db is the path to a file containing the expected schema;
                            actual schema is read from stdin if --db is not provided)

    Examples:
        tycoon ai pipeline document-staging --model trips
        tycoon ai pipeline fix-nulls --model events --dry-run
        tycoon ai pipeline review-staging --model rides --db data/raw.duckdb
        tycoon ai pipeline debug-pipeline --model my_source --db error.log
        tycoon ai pipeline drift-check --model pokemon --db expected_schema.txt
    """
    _ensure_ready()

    if name not in _AVAILABLE_PIPELINES:
        error(f"Unknown pipeline: '{name}'")
        info(f"Available pipelines: {', '.join(_AVAILABLE_PIPELINES)}")
        raise typer.Exit(1)

    # debug-pipeline and drift-check do not profile a DuckDB table
    if name == "debug-pipeline":
        error_output = Path(db_path).read_text() if db_path else ""
        pipeline, initial_inputs = _build_debug_pipeline_pipeline(
            pipeline_name=model,
            error_output=error_output,
            source_config="",
            project_root=config.root,
            dry_run=dry_run,
        )
    elif name == "drift-check":
        expected_schema = Path(db_path).read_text() if db_path else ""
        import sys
        actual_schema = sys.stdin.read() if not sys.stdin.isatty() else ""
        pipeline, initial_inputs = _build_drift_check_pipeline(
            expected_schema=expected_schema,
            actual_schema=actual_schema,
            source_name=model,
            project_root=config.root,
            dry_run=dry_run,
        )
    else:
        from tycoon.ai.profiler import profile_table

        resolved_db = Path(db_path) if db_path else config.raw_db
        info(f"Profiling table '{schema}.{model}' in {resolved_db} ...")

        profile = profile_table(
            db_path=resolved_db,
            schema_name=schema,
            table_name=model,
        )

        if profile is None:
            error(
                f"Table '{schema}.{model}' was not found in {resolved_db}.\n"
                f"  Make sure the table exists and the database path is correct.\n"
                f"  Run 'tycoon run' to ingest data first if needed."
            )
            raise typer.Exit(1)

        profile_summary = profile.summary()
        model_path = f"models/staging/stg_{model}.sql"

        if name == "document-staging":
            pipeline, initial_inputs = _build_document_staging_pipeline(
                model_name=model,
                profile_summary=profile_summary,
                model_path=model_path,
                project_root=config.root,
                dry_run=dry_run,
            )
        elif name == "fix-nulls":
            model_sql_path = config.dbt_project_dir / model_path
            model_sql = model_sql_path.read_text() if model_sql_path.exists() else ""
            pipeline, initial_inputs = _build_fix_nulls_pipeline(
                model_name=model,
                profile_summary=profile_summary,
                model_sql=model_sql,
                model_path=model_path,
                project_root=config.root,
                dry_run=dry_run,
            )
        elif name == "review-staging":
            model_sql_path = config.dbt_project_dir / model_path
            model_sql = model_sql_path.read_text() if model_sql_path.exists() else ""
            pipeline, initial_inputs = _build_review_staging_pipeline(
                model_name=model,
                profile_summary=profile_summary,
                model_sql=model_sql,
                model_path=model_path,
                project_root=config.root,
                dry_run=dry_run,
            )

    # Derive step names from the pipeline's worker instances
    step_names = [worker.name for worker, _ in pipeline.steps]

    if dry_run:
        warn("Dry run: proposals will be shown but not written to disk.")

    info(f"Running pipeline '{name}' ({len(step_names)} steps) ...")
    results = pipeline.run(initial_inputs)

    total_steps = len(results)
    passed_steps = sum(1 for r in results if r.success)
    total_files = sum(len(r.proposals) for r in results if r.success)

    console.print()

    for i, result in enumerate(results):
        step_label = step_names[i] if i < len(step_names) else f"Step {i + 1}"

        if result.success:
            written_paths = [p.path for p in result.proposals]
            if dry_run:
                label = f"[dim](dry-run)[/dim] {len(result.proposals)} proposal(s)"
            else:
                label = f"{len(result.proposals)} file(s) written"
            success(f"[{i + 1}/{total_steps}] {step_label}: {label}")
            for path in written_paths:
                console.print(f"    [dim]{path}[/dim]")
        else:
            error(f"[{i + 1}/{total_steps}] {step_label}: FAILED")
            console.print(f"    {result.message}")
            console.print()
            error(f"Pipeline '{name}' halted at step {i + 1}.")
            raise typer.Exit(1)

    console.print()
    if dry_run:
        info(
            f"Pipeline '{name}' complete ({passed_steps}/{total_steps} steps, "
            f"{total_files} proposal(s) — dry run, nothing written)."
        )
    else:
        success(
            f"Pipeline '{name}' complete: "
            f"{passed_steps}/{total_steps} steps passed, "
            f"{total_files} file(s) written."
        )
