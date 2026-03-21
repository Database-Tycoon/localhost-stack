"""Tests for tycoon AI memory — read/write, proposal parsing, CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tycoon.ai.memory import (
    MEMORY_DIR,
    MEMORY_FILE,
    append_memory,
    get_memory_path,
    parse_memory_proposals,
    read_memory,
    write_memory,
)
from tycoon.ai.context import ProjectContext, gather_context
from tycoon.ai.prompts import build_system_prompt
from tycoon.cli import app


# ---------------------------------------------------------------------------
# get_memory_path
# ---------------------------------------------------------------------------


class TestGetMemoryPath:
    def test_returns_correct_path(self, tmp_path: Path):
        expected = tmp_path / MEMORY_DIR / MEMORY_FILE
        assert get_memory_path(tmp_path) == expected

    def test_path_is_under_tycoon_dir(self, tmp_path: Path):
        path = get_memory_path(tmp_path)
        assert path.parent.name == MEMORY_DIR
        assert path.name == MEMORY_FILE


# ---------------------------------------------------------------------------
# read_memory
# ---------------------------------------------------------------------------


class TestReadMemory:
    def test_returns_empty_string_when_file_missing(self, tmp_path: Path):
        assert read_memory(tmp_path) == ""

    def test_returns_file_contents_when_present(self, tmp_path: Path):
        mem_path = get_memory_path(tmp_path)
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        mem_path.write_text("# Tycoon AI Memory\n- Decision: snake_case columns\n")

        result = read_memory(tmp_path)
        assert "snake_case" in result
        assert "# Tycoon AI Memory" in result


# ---------------------------------------------------------------------------
# write_memory
# ---------------------------------------------------------------------------


class TestWriteMemory:
    def test_creates_directory_and_file(self, tmp_path: Path):
        mem_path = get_memory_path(tmp_path)
        assert not mem_path.exists()

        write_memory(tmp_path, "hello memory")

        assert mem_path.exists()
        assert mem_path.read_text() == "hello memory"

    def test_overwrites_existing_content(self, tmp_path: Path):
        write_memory(tmp_path, "old content")
        write_memory(tmp_path, "new content")
        assert get_memory_path(tmp_path).read_text() == "new content"


# ---------------------------------------------------------------------------
# append_memory
# ---------------------------------------------------------------------------


class TestAppendMemory:
    def test_creates_file_if_not_present(self, tmp_path: Path):
        mem_path = get_memory_path(tmp_path)
        assert not mem_path.exists()

        append_memory(tmp_path, "Decision: use UTC timestamps")

        assert mem_path.exists()
        content = mem_path.read_text()
        assert "use UTC timestamps" in content

    def test_creates_directory_if_missing(self, tmp_path: Path):
        tycoon_dir = tmp_path / MEMORY_DIR
        assert not tycoon_dir.exists()

        append_memory(tmp_path, "a note")

        assert tycoon_dir.is_dir()

    def test_adds_to_existing_file(self, tmp_path: Path):
        write_memory(tmp_path, "# Tycoon AI Memory\n- old entry\n")
        append_memory(tmp_path, "new decision")

        content = get_memory_path(tmp_path).read_text()
        assert "old entry" in content
        assert "new decision" in content

    def test_entry_includes_timestamp(self, tmp_path: Path):
        append_memory(tmp_path, "some note")
        content = get_memory_path(tmp_path).read_text()
        # Timestamp format: [YYYY-MM-DD]
        import re
        assert re.search(r"\[\d{4}-\d{2}-\d{2}\]", content)

    def test_multiple_appends_preserve_all_entries(self, tmp_path: Path):
        append_memory(tmp_path, "first entry")
        append_memory(tmp_path, "second entry")
        append_memory(tmp_path, "third entry")

        content = get_memory_path(tmp_path).read_text()
        assert "first entry" in content
        assert "second entry" in content
        assert "third entry" in content


# ---------------------------------------------------------------------------
# parse_memory_proposals
# ---------------------------------------------------------------------------


class TestParseMemoryProposals:
    def test_extracts_single_block(self):
        response = "Here is my answer.\n\n```memory\nDecision: use snake_case\n```\n"
        proposals = parse_memory_proposals(response)
        assert proposals == ["Decision: use snake_case"]

    def test_extracts_multiple_lines_from_block(self):
        response = "```memory\nDecision: snake_case\nNote: trip_id is surrogate\n```"
        proposals = parse_memory_proposals(response)
        assert len(proposals) == 2
        assert "Decision: snake_case" in proposals
        assert "Note: trip_id is surrogate" in proposals

    def test_extracts_multiple_blocks(self):
        response = (
            "First block:\n```memory\nline one\n```\n"
            "Second block:\n```memory\nline two\n```\n"
        )
        proposals = parse_memory_proposals(response)
        assert "line one" in proposals
        assert "line two" in proposals

    def test_returns_empty_list_when_no_memory_blocks(self):
        response = "Just a normal response with ```python\nprint('hello')\n``` code."
        assert parse_memory_proposals(response) == []

    def test_returns_empty_list_for_empty_response(self):
        assert parse_memory_proposals("") == []

    def test_ignores_blank_lines_inside_block(self):
        response = "```memory\n\nDecision: valid entry\n\n```"
        proposals = parse_memory_proposals(response)
        assert proposals == ["Decision: valid entry"]

    def test_strips_whitespace_from_entries(self):
        response = "```memory\n   padded entry   \n```"
        proposals = parse_memory_proposals(response)
        assert proposals == ["padded entry"]


# ---------------------------------------------------------------------------
# build_system_prompt — memory integration
# ---------------------------------------------------------------------------


class TestBuildSystemPromptWithMemory:
    def test_includes_memory_when_present(self):
        ctx = ProjectContext(ai_memory="- Decision: use UTC timestamps\n- Note: trip_id is surrogate key")
        prompt = build_system_prompt(ctx)
        assert "Project Memory" in prompt
        assert "use UTC timestamps" in prompt
        assert "trip_id is surrogate key" in prompt

    def test_omits_memory_section_when_empty(self):
        ctx = ProjectContext(ai_memory="")
        prompt = build_system_prompt(ctx)
        assert "Project Memory" not in prompt

    def test_memory_appears_before_sources(self):
        ctx = ProjectContext(
            sources={"events": "rest_api"},
            ai_memory="Decision: snake_case",
        )
        prompt = build_system_prompt(ctx)
        memory_pos = prompt.find("Project Memory")
        sources_pos = prompt.find("Registered Sources")
        assert memory_pos < sources_pos


# ---------------------------------------------------------------------------
# gather_context — memory integration
# ---------------------------------------------------------------------------


class TestGatherContextWithMemory:
    def test_includes_memory_when_file_exists(self, tmp_path: Path):
        # Write a memory file
        mem_path = get_memory_path(tmp_path)
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        mem_path.write_text("# Memory\n- Decision: UTC everywhere\n")

        ctx = gather_context(
            project_root=tmp_path,
            raw_db=tmp_path / "raw.duckdb",
            warehouse_db=tmp_path / "warehouse.duckdb",
            dbt_dir=tmp_path / "dbt",
        )

        assert "UTC everywhere" in ctx.ai_memory

    def test_memory_is_empty_when_file_missing(self, tmp_path: Path):
        ctx = gather_context(
            project_root=tmp_path,
            raw_db=tmp_path / "raw.duckdb",
            warehouse_db=tmp_path / "warehouse.duckdb",
            dbt_dir=tmp_path / "dbt",
        )
        assert ctx.ai_memory == ""


# ---------------------------------------------------------------------------
# CLI: tycoon ai memory commands
# ---------------------------------------------------------------------------


class TestMemoryShowCommand:
    def test_shows_memory_when_file_exists(self, cli_runner, tmp_path: Path):
        mem_path = get_memory_path(tmp_path)
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        mem_path.write_text("# Tycoon AI Memory\n- Decision: snake_case\n")

        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "show"])

        assert result.exit_code == 0
        assert "snake_case" in result.stdout

    def test_shows_message_when_no_memory_file(self, cli_runner, tmp_path: Path):
        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "show"])

        assert result.exit_code == 0
        assert "No AI memory" in result.stdout or "memory add" in result.stdout


class TestMemoryAddCommand:
    def test_adds_note_to_memory(self, cli_runner, tmp_path: Path):
        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "add", "Decision: use UTC"])

        assert result.exit_code == 0
        content = get_memory_path(tmp_path).read_text()
        assert "use UTC" in content

    def test_success_message_includes_note(self, cli_runner, tmp_path: Path):
        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "add", "my note here"])

        assert result.exit_code == 0
        assert "my note here" in result.stdout


class TestMemoryClearCommand:
    def test_clears_memory_with_yes_flag(self, cli_runner, tmp_path: Path):
        write_memory(tmp_path, "some important memory")

        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "clear", "--yes"])

        assert result.exit_code == 0
        assert get_memory_path(tmp_path).read_text() == ""

    def test_does_nothing_when_no_file(self, cli_runner, tmp_path: Path):
        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "clear", "--yes"])

        assert result.exit_code == 0
        assert "nothing to clear" in result.stdout or "No AI memory" in result.stdout

    def test_aborts_when_user_declines(self, cli_runner, tmp_path: Path):
        write_memory(tmp_path, "important memory")

        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            # Answer "n" to the confirmation prompt
            result = cli_runner.invoke(app, ["ai", "memory", "clear"], input="n\n")

        assert result.exit_code == 0
        # Memory should still be present
        assert get_memory_path(tmp_path).read_text() == "important memory"


class TestMemoryPathCommand:
    def test_prints_memory_file_path(self, cli_runner, tmp_path: Path):
        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "path"])

        assert result.exit_code == 0
        # Strip newlines inserted by Rich console word-wrap before asserting.
        output_flat = result.stdout.replace("\n", "")
        expected_path = str(get_memory_path(tmp_path)).replace("\n", "")
        assert expected_path in output_flat

    def test_path_ends_with_memory_file(self, cli_runner, tmp_path: Path):
        with patch("tycoon.commands.ai.config") as mock_config:
            mock_config.root = tmp_path
            result = cli_runner.invoke(app, ["ai", "memory", "path"])

        assert MEMORY_FILE in result.stdout
