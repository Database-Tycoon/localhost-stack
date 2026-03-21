"""Agentic dbt test fix loop.

Runs dbt tests, feeds failures to the AI, applies proposed file changes,
and repeats until all tests pass or the attempt limit is reached.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tycoon.ai.client import chat
from tycoon.ai.file_proposals import parse_proposals
from tycoon.utils.console import console, info, success, warn, error


# Matches model names from dbt output lines like:
#   Failure in test not_null_trips_trip_id (models/staging/stg_trips.sql)
#   FAIL 1 not_null_trips_trip_id ....../models/staging/stg_trips.sql
_MODEL_NAME_PATTERN = re.compile(
    r"(?:Failure in test\s+\S+\s+\(|FAIL\s+\d+\s+\S+\s+\S+/)"
    r"(?:models/[\w/]+\.sql)"
    r"|models/([\w/]+\.sql)"
)

# Simpler: find any token ending in .sql that looks like a models path
_SQL_PATH_PATTERN = re.compile(r"models/[\w./\-]+\.sql")


def _parse_failure_models(dbt_output: str, dbt_dir: Path) -> list[Path]:
    """Extract model file Paths from dbt failure output.

    Scans stdout+stderr for tokens that match ``models/...sql`` and
    resolves them relative to *dbt_dir*.  Duplicate paths are removed
    while preserving first-seen order.
    """
    seen: dict[str, Path] = {}
    for match in _SQL_PATH_PATTERN.finditer(dbt_output):
        rel = match.group(0)
        candidate = dbt_dir / rel
        if rel not in seen:
            seen[rel] = candidate
    return list(seen.values())


def _backup_and_write(path: Path, content: str) -> None:
    """Back up *path* to ``<path>.bak`` then write *content* in place.

    If the original file does not exist the backup is not created, but
    the new content is still written (creating the file).
    """
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        bak.write_text(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _restore_backups(backed_up: list[Path]) -> None:
    """Restore every file in *backed_up* from its ``.bak`` sibling.

    Files without a corresponding ``.bak`` are left untouched.
    """
    for path in backed_up:
        bak = path.with_suffix(path.suffix + ".bak")
        if bak.exists():
            path.write_text(bak.read_text())
            bak.unlink()


def run_fix_loop(
    dbt_dir: Path,
    project_root: Path,
    system_prompt: str,
    model: str | None = None,
    max_attempts: int = 3,
    target: str = "local",
    select: str | None = None,
) -> bool:
    """Run the agentic dbt test fix loop.

    Executes dbt tests, feeds failures to the AI, applies proposed file
    changes, and repeats until all tests pass or *max_attempts* is reached.

    Args:
        dbt_dir: Path to the dbt project directory (contains ``dbt_project.yml``).
        project_root: Working directory for subprocess invocations.
        system_prompt: System prompt prepended to every AI request.
        model: LM Studio model override (``None`` uses the loaded model).
        max_attempts: Maximum number of fix-and-retest cycles.
        target: dbt ``--target`` profile name.
        select: Optional dbt ``--select`` expression to narrow the test scope.

    Returns:
        ``True`` if all tests pass, ``False`` if the limit is reached without
        all tests passing (backed-up files are restored before returning).
    """
    backed_up: list[Path] = []

    for attempt in range(1, max_attempts + 1):
        console.print(
            f"\n[bold cyan]Fix attempt {attempt}/{max_attempts}[/bold cyan] — running dbt tests..."
        )

        # ------------------------------------------------------------------ #
        # Step 1: Run dbt tests
        # ------------------------------------------------------------------ #
        cmd: list[str] = [
            "dbt",
            "test",
            "--project-dir", str(dbt_dir),
            "--profiles-dir", str(dbt_dir),
            "--target", target,
        ]
        if select:
            cmd += ["--select", select]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        combined_output = result.stdout + result.stderr

        # ------------------------------------------------------------------ #
        # Step 2: All tests pass → done
        # ------------------------------------------------------------------ #
        if result.returncode == 0:
            success("All dbt tests pass.")
            return True

        console.print(f"[yellow]Tests failed (exit {result.returncode}). Asking AI for fixes...[/yellow]")

        # ------------------------------------------------------------------ #
        # Step 3: Parse failure output for model file references
        # ------------------------------------------------------------------ #
        failure_models = _parse_failure_models(combined_output, dbt_dir)

        # ------------------------------------------------------------------ #
        # Step 4: Build the AI message
        # ------------------------------------------------------------------ #
        model_context_parts: list[str] = []
        for model_path in failure_models:
            if model_path.exists():
                model_context_parts.append(
                    f"### {model_path.relative_to(dbt_dir)}\n"
                    f"```sql\n{model_path.read_text().strip()}\n```"
                )

        model_context = (
            "\n\n## Relevant dbt Model Files\n\n" + "\n\n".join(model_context_parts)
            if model_context_parts
            else ""
        )

        user_content = (
            "## dbt Test Output\n\n"
            f"```\n{combined_output.strip()}\n```"
            f"{model_context}\n\n"
            "Fix the failing dbt tests. Propose file changes using fenced code blocks "
            "with the file path as the language identifier."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # ------------------------------------------------------------------ #
        # Step 5: Call the AI
        # ------------------------------------------------------------------ #
        info("Waiting for AI response...")
        try:
            ai_response = chat(messages, model=model)
        except Exception as exc:
            error(f"AI request failed: {exc}")
            _restore_backups(backed_up)
            return False

        console.print()
        console.print(ai_response)

        # ------------------------------------------------------------------ #
        # Step 6: Parse and apply proposals
        # ------------------------------------------------------------------ #
        proposals = parse_proposals(ai_response)
        if not proposals:
            warn("AI returned no file proposals. Cannot auto-fix.")
            _restore_backups(backed_up)
            return False

        console.print(f"\n[bold]{len(proposals)} file proposal(s) detected — applying...[/bold]")
        for proposal in proposals:
            target_path = Path(proposal.path)
            if not target_path.is_absolute():
                target_path = project_root / target_path

            # On the first encounter, back up the original so we can restore
            # it later.  On subsequent encounters (later fix attempts) we only
            # overwrite the live file — the first backup is intentionally
            # preserved so _restore_backups can recover the true original.
            if target_path not in backed_up:
                _backup_and_write(target_path, proposal.content)
                backed_up.append(target_path)
            else:
                # Already have a backup — just update the live file.
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(proposal.content)
            info(f"Applied fix: {proposal.path}")

    # ---------------------------------------------------------------------- #
    # Exhausted all attempts — restore originals and report failure
    # ---------------------------------------------------------------------- #
    warn(f"Max attempts ({max_attempts}) reached without all tests passing.")
    _restore_backups(backed_up)
    return False
