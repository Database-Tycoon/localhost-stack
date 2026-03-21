"""Project AI memory — persistent decisions and notes across sessions.

The memory file lives at ``<project_root>/.tycoon/ai_memory.md`` and is
intended to be committed to version control. It captures project-specific
decisions, conventions, and notes so the LLM has stable context across
chat sessions.

LLM responses can propose new memory entries using a fenced ``memory``
block::

    ```memory
    Decision: use snake_case for all column names
    ```

These are parsed by :func:`parse_memory_proposals` and, if accepted by
the user, appended via :func:`append_memory`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

MEMORY_DIR = ".tycoon"
MEMORY_FILE = "ai_memory.md"

_INITIAL_CONTENT = """\
# Tycoon AI Memory
Project decisions, conventions, and notes that persist across sessions.

## Decisions

## Notes
"""


def get_memory_path(project_root: Path) -> Path:
    """Return the path to the project AI memory file."""
    return project_root / MEMORY_DIR / MEMORY_FILE


def read_memory(project_root: Path) -> str:
    """Read the AI memory file. Returns empty string if not found."""
    path = get_memory_path(project_root)
    if not path.exists():
        return ""
    return path.read_text()


def write_memory(project_root: Path, content: str) -> None:
    """Write the AI memory file, creating the .tycoon/ directory if needed."""
    path = get_memory_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def append_memory(project_root: Path, entry: str) -> None:
    """Append a new entry (with timestamp) to the AI memory file.

    If the file does not exist it is created with the standard header.
    The entry is stamped with today's date and appended at the end of the
    file (after any existing content).

    Parameters
    ----------
    project_root:
        Root directory of the tycoon project.
    entry:
        A short, human-readable note or decision to persist.
    """
    path = get_memory_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    stamped_entry = f"- [{today}] {entry.strip()}"

    if not path.exists():
        content = _INITIAL_CONTENT.rstrip("\n") + f"\n{stamped_entry}\n"
        path.write_text(content)
        return

    existing = path.read_text()
    # Append after the last non-blank line, preserving a trailing newline.
    updated = existing.rstrip("\n") + f"\n{stamped_entry}\n"
    path.write_text(updated)


def parse_memory_proposals(response: str) -> list[str]:
    """Extract memory entries from an LLM response.

    The AI can propose memory additions using a special fenced block::

        ```memory
        Decision: use snake_case for all column names
        ```

    Multiple blocks may appear in a single response. Each non-blank line
    inside a block becomes a separate proposal.

    Parameters
    ----------
    response:
        Raw text returned by the LLM.

    Returns
    -------
    list[str]
        List of proposed memory entries (stripped of leading/trailing
        whitespace). Empty list when no ``memory`` blocks are present.
    """
    pattern = re.compile(r"```memory\s*\n(.*?)```", re.DOTALL)
    proposals: list[str] = []
    for match in pattern.finditer(response):
        block = match.group(1)
        for line in block.splitlines():
            stripped = line.strip()
            if stripped:
                proposals.append(stripped)
    return proposals
