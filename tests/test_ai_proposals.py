"""Tests for file proposal parsing and the ask command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tycoon.ai.file_proposals import FileProposal, parse_proposals
from tycoon.ai.client import LMStudioStatus, ModelInfo
from tycoon.cli import app


# ---------------------------------------------------------------------------
# parse_proposals
# ---------------------------------------------------------------------------


class TestParseProposals:
    def test_extracts_file_path_blocks(self):
        response = """\
Here's the staging model:

```dbt_project/models/staging/stg_events.sql
SELECT * FROM {{ source('raw', 'events') }}
```

And the schema:

```dbt_project/models/staging/_events__models.yml
version: 2
models:
  - name: stg_events
```
"""
        proposals = parse_proposals(response)
        assert len(proposals) == 2
        assert proposals[0].path == "dbt_project/models/staging/stg_events.sql"
        assert "source('raw', 'events')" in proposals[0].content
        assert proposals[1].path == "dbt_project/models/staging/_events__models.yml"

    def test_ignores_plain_language_blocks(self):
        response = """\
Here's an example:

```sql
SELECT 1
```

```python
print("hello")
```
"""
        proposals = parse_proposals(response)
        assert len(proposals) == 0

    def test_handles_no_code_blocks(self):
        response = "Just some plain text without any code blocks."
        proposals = parse_proposals(response)
        assert len(proposals) == 0

    def test_handles_mixed_blocks(self):
        response = """\
Explanation:

```sql
SELECT * FROM raw.events
```

Here's the file:

```models/stg_events.sql
SELECT * FROM {{ source('raw', 'events') }}
```
"""
        proposals = parse_proposals(response)
        assert len(proposals) == 1
        assert proposals[0].path == "models/stg_events.sql"

    def test_preserves_content_whitespace(self):
        response = """\
```src/test.py
def hello():
    print("hello")

    return True
```
"""
        proposals = parse_proposals(response)
        assert len(proposals) == 1
        assert "    print" in proposals[0].content
        assert "\n\n    return True\n" in proposals[0].content

    def test_dotfile_treated_as_path(self):
        response = """\
```tycoon.yml
name: test
```
"""
        proposals = parse_proposals(response)
        assert len(proposals) == 1
        assert proposals[0].path == "tycoon.yml"


# ---------------------------------------------------------------------------
# ask command
# ---------------------------------------------------------------------------


class TestAskCommand:
    def _mock_ready(self):
        return LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test-model", state="loaded")],
        )

    def test_dry_run_shows_prompt(self, cli_runner):
        result = cli_runner.invoke(app, ["ai", "ask", "--dry-run", "--no-context", "hello"])
        assert result.exit_code == 0
        assert "System prompt" in result.stdout
        assert "data pipeline assistant" in result.stdout

    def test_dry_run_with_context(self, cli_runner, tmp_config):
        with patch("tycoon.commands.ai.config", tmp_config):
            result = cli_runner.invoke(app, ["ai", "ask", "--dry-run", "hello"])
            assert result.exit_code == 0
            assert "System prompt" in result.stdout

    def test_ask_sends_to_lm_studio(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=self._mock_ready()),
            patch("tycoon.commands.ai.chat", return_value="Here is my answer.") as mock_chat,
        ):
            result = cli_runner.invoke(app, ["ai", "ask", "--no-context", "test question"])
            assert result.exit_code == 0
            assert "Here is my answer." in result.stdout
            mock_chat.assert_called_once()
            messages = mock_chat.call_args[0][0]
            assert messages[1]["content"] == "test question"

    def test_ask_fails_when_server_down(self, cli_runner):
        with patch("tycoon.commands.ai.get_status", return_value=LMStudioStatus(running=False)):
            result = cli_runner.invoke(app, ["ai", "ask", "hello"])
            assert result.exit_code == 1

    def test_ask_with_model_override(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=self._mock_ready()),
            patch("tycoon.commands.ai.chat", return_value="ok") as mock_chat,
        ):
            result = cli_runner.invoke(app, ["ai", "ask", "--no-context", "-m", "custom-model", "hi"])
            assert result.exit_code == 0
            assert mock_chat.call_args[1]["model"] == "custom-model"

    def test_ask_writes_proposals_with_yes(self, cli_runner, tmp_path):
        response = f"""\
Here's your model:

```{tmp_path}/test_output.sql
SELECT 1 AS id
```
"""
        with (
            patch("tycoon.commands.ai.get_status", return_value=self._mock_ready()),
            patch("tycoon.commands.ai.chat", return_value=response),
        ):
            result = cli_runner.invoke(app, ["ai", "ask", "--no-context", "-y", "write a model"])
            assert result.exit_code == 0
            assert (tmp_path / "test_output.sql").exists()
            assert "SELECT 1 AS id" in (tmp_path / "test_output.sql").read_text()

    def test_ask_no_proposals_without_yes(self, cli_runner):
        response = """\
Here's your model:

```models/test.sql
SELECT 1
```
"""
        with (
            patch("tycoon.commands.ai.get_status", return_value=self._mock_ready()),
            patch("tycoon.commands.ai.chat", return_value=response),
        ):
            # Without --yes, the prompt will default to "n" in non-interactive mode
            result = cli_runner.invoke(app, ["ai", "ask", "--no-context", "write a model"], input="n\n")
            assert result.exit_code == 0
            assert "Skipped" in result.stdout

    def test_ask_handles_lm_studio_error(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=self._mock_ready()),
            patch("tycoon.commands.ai.chat", side_effect=Exception("connection refused")),
        ):
            result = cli_runner.invoke(app, ["ai", "ask", "--no-context", "hello"])
            assert result.exit_code == 1
            assert "failed" in result.stdout.lower() or "failed" in (result.stderr or "").lower()
