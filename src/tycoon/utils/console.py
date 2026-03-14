"""Rich output helpers."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
err_console = Console(stderr=True)


def status_table(rows: list[tuple[str, str, str]], title: str = "Status") -> Table:
    """Build a Rich table with Component / Status / Detail columns."""
    table = Table(title=title, show_lines=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Detail", style="dim")
    for component, status, detail in rows:
        style = "green" if status == "OK" else "red" if status == "FAIL" else "yellow"
        table.add_row(component, f"[{style}]{status}[/{style}]", detail)
    return table


def success(msg: str) -> None:
    console.print(f"[green bold]OK[/] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow bold]WARN[/] {msg}")


def error(msg: str) -> None:
    err_console.print(f"[red bold]ERROR[/] {msg}")


def info(msg: str) -> None:
    console.print(f"[blue]>[/] {msg}")


def header(msg: str) -> None:
    console.print(Panel(msg, style="bold cyan"))
