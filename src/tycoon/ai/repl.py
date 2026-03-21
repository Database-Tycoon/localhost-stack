"""Interactive chat REPL for the AI assistant.

Provides a conversational interface with streaming responses,
command history, and slash commands.
"""

from __future__ import annotations

from pathlib import Path

from tycoon.ai.client import chat, chat_stream
from tycoon.ai.file_proposals import parse_proposals
from tycoon.ai.memory import append_memory, parse_memory_proposals
from tycoon.utils.console import console, error, info, success


SLASH_COMMANDS = {
    "/quit": "Exit the chat session",
    "/clear": "Clear conversation history (keep system prompt)",
    "/context": "Show the current system prompt",
    "/help": "Show available commands",
}


def _handle_slash_command(
    cmd: str,
    messages: list[dict[str, str]],
    system_prompt: str,
) -> bool | None:
    """Handle a slash command. Returns True to continue, False to quit, None if not a command."""
    cmd = cmd.strip().lower()
    if cmd not in SLASH_COMMANDS:
        return None

    if cmd == "/quit":
        return False

    if cmd == "/clear":
        # Keep only the system message
        messages.clear()
        messages.append({"role": "system", "content": system_prompt})
        info("Conversation cleared")
        return True

    if cmd == "/context":
        console.print(f"\n[dim]{system_prompt[:2000]}[/dim]")
        if len(system_prompt) > 2000:
            console.print(f"[dim]... ({len(system_prompt):,} chars total)[/dim]")
        return True

    if cmd == "/help":
        for name, desc in SLASH_COMMANDS.items():
            console.print(f"  [bold]{name}[/bold]  {desc}")
        return True

    return None


def _write_proposals(response: str, project_root: Path, auto_accept: bool = False) -> None:
    """Parse and optionally write file proposals from a response."""
    proposals = parse_proposals(response)
    if not proposals:
        return

    console.print(f"\n[bold]{len(proposals)} file proposal(s) detected[/bold]")
    for proposal in proposals:
        if auto_accept:
            accept = True
        else:
            console.print(f"\n[bold cyan]Proposed file:[/bold cyan] {proposal.path}")
            console.print("─" * 60)
            for i, line in enumerate(proposal.content.splitlines(), 1):
                console.print(f"[dim]{i:3d}[/dim] {line}")
            console.print("─" * 60)
            try:
                choice = console.input("[bold]Write? [y/n]:[/bold] ").strip().lower()
            except EOFError:
                choice = "n"
            accept = choice in ("y", "yes")

        if accept:
            target = Path(proposal.path)
            if not target.is_absolute():
                target = project_root / target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(proposal.content)
            success(f"Wrote {proposal.path}")
        else:
            info(f"Skipped {proposal.path}")


def run_repl(
    system_prompt: str,
    project_root: Path,
    model: str | None = None,
    auto_accept: bool = False,
    stream: bool = True,
) -> None:
    """Run the interactive chat REPL.

    Parameters
    ----------
    system_prompt:
        The context-rich system prompt to use for the conversation.
    project_root:
        Project root directory for resolving relative file paths.
    model:
        Optional model override.
    auto_accept:
        Auto-accept file proposals without prompting.
    stream:
        Use streaming responses (prints tokens as they arrive).
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    console.print("[bold]Tycoon AI Chat[/bold] — type /help for commands, /quit to exit\n")

    while True:
        try:
            user_input = console.input("[bold green]you>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not user_input:
            continue

        # Check for slash commands
        if user_input.startswith("/"):
            result = _handle_slash_command(user_input, messages, system_prompt)
            if result is False:
                break
            if result is True:
                continue
            # Not a recognized command — treat as normal input

        messages.append({"role": "user", "content": user_input})

        if stream:
            try:
                console.print("\n[bold blue]ai>[/bold blue] ", end="")
                chunks: list[str] = []
                for chunk in chat_stream(messages, model=model):
                    console.print(chunk, end="")
                    chunks.append(chunk)
                console.print("\n")
                response = "".join(chunks)
            except Exception as exc:
                console.print()
                error(f"Request failed: {exc}")
                messages.pop()
                continue
        else:
            try:
                response = chat(messages, model=model)
            except Exception as exc:
                error(f"Request failed: {exc}")
                messages.pop()
                continue
            console.print(f"\n[bold blue]ai>[/bold blue] {response}\n")

        messages.append({"role": "assistant", "content": response})

        # Check for file proposals
        _write_proposals(response, project_root, auto_accept)

        # Check for memory proposals
        memory_proposals = parse_memory_proposals(response)
        for entry in memory_proposals:
            console.print(f"\n[bold yellow]Memory proposal:[/bold yellow] {entry}")
            try:
                choice = console.input("[bold]Add to project memory? [y/n]:[/bold] ").strip().lower()
            except EOFError:
                choice = "n"
            if choice in ("y", "yes"):
                append_memory(project_root, entry)
                info("Added to project memory.")
