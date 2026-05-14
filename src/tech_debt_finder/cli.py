"""
cli.py — The entry point for our tool

This is like main.dart in Flutter. When you run 'tech-debt-finder scan',
Python looks at pyproject.toml, sees that 'tech-debt-finder' command
should run 'tech_debt_finder.cli:app', and executes this file.

TYPER BASICS:
- typer.Typer() creates an "app" that handles commands
- @app.command() decorator turns a function into a CLI command
- Function parameters become CLI flags/arguments automatically

Example:
    def scan(path: str = "."):
    
    This creates: tech-debt-finder scan --path ./my-folder
    The '= "."' means path defaults to current directory
"""

import typer
from rich.console import Console

# Create the CLI app — this is like the "router" for commands
app = typer.Typer(
    name="tech-debt-finder",
    help="Find and prioritize stale TODOs, FIXMEs, and code rot in your codebase.",
    add_completion=False,  # Don't add shell completion (keeps it simple)
)

# Rich console for pretty output (colors, tables, etc.)
# We'll use this everywhere instead of print()
console = Console()


@app.command()
def scan(
    path: str = typer.Argument(
        ".", 
        help="Path to scan (file or directory). Defaults to current directory."
    ),
    age: int = typer.Option(
        0,
        "--age", "-a",
        help="Minimum age in days. Only show markers older than this."
    ),
    json_output: bool = typer.Option(
        False,
        "--json", "-j",
        help="Output as JSON (for snapshots and CI integration)."
    ),
    analyze: bool = typer.Option(
        False,
        "--analyze",
        help="Use AI to group TODOs by theme and explain priorities."
    ),
):
    """
    Scan for TODOs, FIXMEs, and code rot.
    
    Examples:
        tech-debt-finder scan
        tech-debt-finder scan ./src --age 180
        tech-debt-finder scan --json > snapshot.json
        tech-debt-finder scan --analyze
    """
    # For now, just print what we received to confirm CLI works
    console.print(f"[bold blue]🔍 Scanning:[/] {path}")
    console.print(f"[dim]  Age filter: {age} days[/]")
    console.print(f"[dim]  JSON output: {json_output}[/]")
    console.print(f"[dim]  AI analysis: {analyze}[/]")
    console.print()
    console.print("[yellow]⚠ Scanner not implemented yet — coming next![/]")


@app.command()
def trend(
    file1: str = typer.Argument(..., help="First snapshot file (older)"),
    file2: str = typer.Argument(..., help="Second snapshot file (newer)"),
):
    """
    Compare two snapshots to see trend over time.
    
    Example:
        tech-debt-finder trend snapshot-may-01.json snapshot-may-14.json
    """
    console.print(f"[bold blue]📈 Comparing:[/] {file1} → {file2}")
    console.print("[yellow]⚠ Trend comparison not implemented yet![/]")


@app.command()
def version():
    """Show version information."""
    from tech_debt_finder import __version__
    console.print(f"tech-debt-finder version [bold green]{__version__}[/]")


# This allows running the file directly: python -m tech_debt_finder.cli
if __name__ == "__main__":
    app()
