"""
reporter.py — Pretty terminal output for scan results

Uses the Rich library to display:
- Colored priority indicators (🔴 HIGH, 🟡 MEDIUM, 🟢 LOW)
- Tables with markers grouped by priority
- Summary statistics
- Dormant file warnings

RICH BASICS
===========
Rich uses markup tags for styling, similar to HTML:

    console.print("[bold]Bold text[/bold]")
    console.print("[red]Red text[/red]")
    console.print("[bold blue]Bold blue[/bold blue]")
    console.print("[dim]Dimmed/gray text[/dim]")

You can also combine:
    console.print("[bold red]Error![/bold red] Something went wrong")

Tables are created with the Table class:
    table = Table(title="My Table")
    table.add_column("Name")
    table.add_column("Value")
    table.add_row("foo", "bar")
    console.print(table)
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from tech_debt_finder.scanner import Marker, count_by_type
from tech_debt_finder.prioritizer import group_by_priority


# Create a console instance — we'll use this everywhere
# You can also create it in cli.py and pass it in, but a module-level
# instance is simpler for now
console = Console()


# =============================================================================
# COLOR SCHEME
# =============================================================================

# Priority colors
PRIORITY_COLORS = {
    "high": "red",
    "medium": "yellow",
    "low": "green",
}

# Priority icons
PRIORITY_ICONS = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}

# Marker type colors
TYPE_COLORS = {
    "TODO": "cyan",
    "FIXME": "red",
    "HACK": "magenta",
    "TEMP": "yellow",
    "XXX": "red",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_age(age_days: int) -> str:
    """
    Format age in a human-readable way.
    
    Examples:
        format_age(0) → "today"
        format_age(1) → "1d"
        format_age(30) → "30d"
        format_age(365) → "1y"
        format_age(730) → "2y"
    """
    if age_days == 0:
        return "today"
    elif age_days < 365:
        return f"{age_days}d"
    else:
        years = age_days // 365
        return f"{years}y"


def truncate(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_file_path(file_path: str, max_length: int = 40) -> str:
    """
    Format file path for display.
    Shows just the filename if path is too long.
    """
    if len(file_path) <= max_length:
        return file_path
    
    # Try showing just the filename
    name = Path(file_path).name
    if len(name) <= max_length:
        return name
    
    # Truncate the filename itself
    return truncate(name, max_length)


# =============================================================================
# MAIN REPORT FUNCTIONS
# =============================================================================

def print_marker_table(
    markers: list[Marker], 
    title: str,
    priority: str,
    show_all: bool = False,
    max_rows: int = 10,
) -> None:
    """
    Print a table of markers for a specific priority level.
    
    Args:
        markers: List of markers to display
        title: Table title
        priority: Priority level (for coloring)
        show_all: If True, show all markers. If False, limit to max_rows.
        max_rows: Maximum rows to show when show_all is False
    """
    if not markers:
        return
    
    color = PRIORITY_COLORS.get(priority, "white")
    icon = PRIORITY_ICONS.get(priority, "•")
    
    # Create table
    table = Table(
        title=f"{icon} {title} ({len(markers)})",
        title_style=f"bold {color}",
        border_style=color,
        show_lines=False,
    )
    
    # Add columns
    table.add_column("File", style="green", max_width=40)
    table.add_column("Line", justify="right", style="dim")
    table.add_column("Type", style="cyan", width=6)
    table.add_column("Message", style="white")
    table.add_column("Age", justify="right", style="yellow")
    table.add_column("Author", style="dim", max_width=15)
    
    # Determine which markers to show
    display_markers = markers if show_all else markers[:max_rows]
    
    # Add rows
    for marker in display_markers:
        type_color = TYPE_COLORS.get(marker.marker_type, "white")
        
        table.add_row(
            format_file_path(marker.file),
            str(marker.line),
            f"[{type_color}]{marker.marker_type}[/{type_color}]",
            truncate(marker.text, 40),
            format_age(marker.age_days),
            truncate(marker.author, 15),
        )
    
    console.print(table)
    
    # Show "and X more" if truncated
    if not show_all and len(markers) > max_rows:
        remaining = len(markers) - max_rows
        console.print(f"[dim]  ... and {remaining} more[/dim]\n")
    else:
        console.print()  # Blank line after table


def print_summary(markers: list[Marker], scan_path: str) -> None:
    """
    Print summary statistics at the end of the report.
    """
    # Group by priority
    groups = group_by_priority(markers)
    high_count = len(groups["high"])
    medium_count = len(groups["medium"])
    low_count = len(groups["low"])
    
    # Get counts by type
    type_counts = count_by_type(markers)
    
    # Find oldest marker
    oldest_age = max((m.age_days for m in markers), default=0)
    
    # Build summary text
    summary_lines = [
        f"[bold]Total markers:[/bold] {len(markers)}",
        f"[red]High priority:[/red] {high_count}",
        f"[yellow]Medium priority:[/yellow] {medium_count}",
        f"[green]Low priority:[/green] {low_count}",
        "",
        "[bold]By type:[/bold] " + ", ".join(
            f"{t}: {c}" for t, c in sorted(type_counts.items())
        ),
        "",
        f"[bold]Oldest:[/bold] {format_age(oldest_age)}" if oldest_age > 0 else "",
    ]
    
    # Remove empty lines at the end
    while summary_lines and not summary_lines[-1]:
        summary_lines.pop()
    
    # Create a panel for the summary
    summary_text = "\n".join(summary_lines)
    panel = Panel(
        summary_text,
        title="📊 Summary",
        title_align="left",
        border_style="blue",
    )
    
    console.print(panel)


def print_report(
    markers: list[Marker],
    scan_path: str = ".",
    show_all: bool = False,
) -> None:
    """
    Print the full tech debt report.
    
    This is the main function called from the CLI.
    
    Args:
        markers: List of markers (should be prioritized already)
        scan_path: Path that was scanned (for display)
        show_all: If True, show all markers. If False, limit each section.
    """
    if not markers:
        console.print("[yellow]No markers found![/yellow]")
        return
    
    # Header
    console.print(f"\n[bold blue]🔍 Tech Debt Report[/bold blue]")
    console.print(f"[dim]Scanned: {scan_path}[/dim]\n")
    
    # Group by priority
    groups = group_by_priority(markers)
    
    # Print each priority group
    # Order: high → medium → low (most important first)
    if groups["high"]:
        print_marker_table(
            groups["high"], 
            "HIGH PRIORITY", 
            "high",
            show_all=show_all,
        )
    
    if groups["medium"]:
        print_marker_table(
            groups["medium"],
            "MEDIUM PRIORITY",
            "medium",
            show_all=show_all,
        )
    
    if groups["low"]:
        print_marker_table(
            groups["low"],
            "LOW PRIORITY",
            "low",
            show_all=show_all,
        )
    
    # Summary at the end
    print_summary(markers, scan_path)


def print_no_markers_found(scan_path: str) -> None:
    """Print a friendly message when no markers are found."""
    console.print(f"\n[bold green]✨ No tech debt markers found![/bold green]")
    console.print(f"[dim]Scanned: {scan_path}[/dim]")
    console.print("[dim]Your codebase is clean (or we're not scanning the right files).[/dim]\n")


# =============================================================================
# PROGRESS INDICATOR
# =============================================================================

def print_scanning_message(path: str) -> None:
    """Print a message indicating we're scanning."""
    console.print(f"[bold blue]🔍 Scanning:[/bold blue] {path}")


def print_enriching_message(count: int) -> None:
    """Print a message indicating we're getting git info."""
    console.print(f"[dim]  Enriching {count} markers with git info...[/dim]")


def print_done_message() -> None:
    """Print a completion message."""
    console.print(f"[dim]  Done![/dim]\n")


# =============================================================================
# DEAD CODE REPORT
# =============================================================================

def print_dead_code_report(commented_blocks: list, dormant_files: list) -> None:
    """
    Print report of commented-out code blocks and dormant files.
    
    Args:
        commented_blocks: List of CommentedCodeBlock objects
        dormant_files: List of DormantFile objects
    """
    total_issues = len(commented_blocks) + len(dormant_files)
    
    if total_issues == 0:
        console.print("\n[green]✨ No dead code found![/green]")
        return
    
    console.print(f"\n[bold red]💀 Dead Code Report[/bold red]")
    console.print(f"[dim]Found {total_issues} potential issues[/dim]\n")
    
    # Commented-out code blocks
    if commented_blocks:
        console.print(f"[bold yellow]📝 Commented-Out Code ({len(commented_blocks)} blocks)[/bold yellow]")
        
        table = Table(show_header=True)
        table.add_column("File", style="green", max_width=40)
        table.add_column("Lines", justify="right", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Preview", style="dim")
        
        for block in commented_blocks[:10]:  # Limit to 10
            table.add_row(
                format_file_path(block.file, 40),
                f"{block.start_line}-{block.end_line}",
                f"{block.line_count} lines",
                truncate(block.preview, 40),
            )
        
        console.print(table)
        
        if len(commented_blocks) > 10:
            console.print(f"[dim]  ... and {len(commented_blocks) - 10} more blocks[/dim]")
        console.print()
    
    # Dormant files
    if dormant_files:
        console.print(f"[bold yellow]🕸️ Dormant Files ({len(dormant_files)} files, no activity in 6+ months)[/bold yellow]")
        
        table = Table(show_header=True)
        table.add_column("File", style="green", max_width=50)
        table.add_column("Last Modified", style="yellow")
        table.add_column("Days Ago", justify="right", style="red")
        table.add_column("Last Author", style="dim")
        
        for df in dormant_files[:10]:  # Limit to 10
            # Format days nicely
            if df.days_since_modified >= 365:
                age_str = f"{df.days_since_modified // 365}y {(df.days_since_modified % 365) // 30}m"
            else:
                age_str = f"{df.days_since_modified}d"
            
            table.add_row(
                format_file_path(df.file, 50),
                df.last_modified_date,
                age_str,
                truncate(df.last_author, 15),
            )
        
        console.print(table)
        
        if len(dormant_files) > 10:
            console.print(f"[dim]  ... and {len(dormant_files) - 10} more files[/dim]")
    
    console.print()


# =============================================================================
# MARKDOWN REPORT GENERATION
# =============================================================================

def generate_markdown_report(
    markers: list[Marker],
    scan_path: str = ".",
    commented_blocks: list | None = None,
    dormant_files: list | None = None,
) -> str:
    """
    Generate a shareable markdown report of tech debt.
    
    Args:
        markers: List of prioritized markers
        scan_path: Path that was scanned
        commented_blocks: Optional list of CommentedCodeBlock objects
        dormant_files: Optional list of DormantFile objects
    
    Returns:
        Markdown string ready to save to a file
    """
    from datetime import datetime
    
    lines = []
    
    # Header
    lines.append("# Tech Debt Report")
    lines.append("")
    lines.append(f"**Scanned:** `{scan_path}`")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    # Summary
    groups = group_by_priority(markers)
    type_counts = count_by_type(markers)
    
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total markers | {len(markers)} |")
    lines.append(f"| 🔴 High priority | {len(groups['high'])} |")
    lines.append(f"| 🟡 Medium priority | {len(groups['medium'])} |")
    lines.append(f"| 🟢 Low priority | {len(groups['low'])} |")
    lines.append("")
    
    # By type
    lines.append("**By type:** " + ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items())))
    lines.append("")
    
    # Helper to format marker table
    def add_marker_table(marker_list: list[Marker], title: str, emoji: str):
        if not marker_list:
            return
        lines.append(f"## {emoji} {title} ({len(marker_list)})")
        lines.append("")
        lines.append("| File | Line | Type | Message | Age | Author |")
        lines.append("|------|------|------|---------|-----|--------|")
        for m in marker_list:
            # Escape pipe characters in message
            msg = m.text.replace("|", "\\|")[:50]
            author = (m.author or "unknown")[:15]
            lines.append(f"| `{format_file_path(m.file, 30)}` | {m.line} | {m.marker_type} | {msg} | {format_age(m.age_days)} | {author} |")
        lines.append("")
    
    # Priority sections
    add_marker_table(groups["high"], "High Priority", "🔴")
    add_marker_table(groups["medium"], "Medium Priority", "🟡")
    add_marker_table(groups["low"], "Low Priority", "🟢")
    
    # Dead code section (if provided)
    if commented_blocks or dormant_files:
        lines.append("## 💀 Dead Code")
        lines.append("")
        
        if commented_blocks:
            lines.append(f"### Commented-Out Code ({len(commented_blocks)} blocks)")
            lines.append("")
            lines.append("| File | Lines | Count | Preview |")
            lines.append("|------|-------|-------|---------|")
            for block in commented_blocks:
                preview = block.preview.replace("|", "\\|")[:40]
                lines.append(f"| `{format_file_path(block.file, 30)}` | {block.start_line}-{block.end_line} | {block.line_count} | {preview} |")
            lines.append("")
        
        if dormant_files:
            lines.append(f"### Dormant Files ({len(dormant_files)} files)")
            lines.append("")
            lines.append("| File | Last Modified | Days Ago | Last Author |")
            lines.append("|------|---------------|----------|-------------|")
            for df in dormant_files:
                lines.append(f"| `{format_file_path(df.file, 40)}` | {df.last_modified_date} | {df.days_since_modified} | {df.last_author[:15]} |")
            lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("*Generated by [tech-debt-finder](https://github.com/your-org/tech-debt-finder)*")
    
    return "\n".join(lines)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Create some fake markers to test the display
    test_markers = [
        Marker(
            file="src/services/auth_service.dart",
            line=142,
            marker_type="TODO",
            text="handle token refresh edge case when session expires",
            full_line="// TODO: handle token refresh edge case",
            author="Alice Smith",
            date="2024-03-15",
            age_days=426,
            file_modifications=34,
            priority_score=0.92,
            priority_bucket="high",
        ),
        Marker(
            file="src/api/profile_api.dart",
            line=89,
            marker_type="FIXME",
            text="this will break if avatar is null",
            full_line="// FIXME: this will break if avatar is null",
            author="Bob Johnson",
            date="2024-01-22",
            age_days=478,
            file_modifications=28,
            priority_score=0.85,
            priority_bucket="high",
        ),
        Marker(
            file="src/utils/helpers.dart",
            line=45,
            marker_type="HACK",
            text="temporary workaround until API v2 is ready",
            full_line="// HACK: temporary workaround",
            author="Carol White",
            date="2024-11-15",
            age_days=180,
            file_modifications=12,
            priority_score=0.55,
            priority_bucket="medium",
        ),
        Marker(
            file="src/deprecated/old_sync.dart",
            line=203,
            marker_type="XXX",
            text="remove this entire file after migration",
            full_line="// XXX: remove this entire file",
            author="departed_employee",
            date="2023-06-01",
            age_days=713,
            file_modifications=0,
            priority_score=0.42,
            priority_bucket="medium",
        ),
        Marker(
            file="src/screens/home_screen.dart",
            line=55,
            marker_type="TODO",
            text="add loading animation",
            full_line="// TODO: add loading animation",
            author="Alice Smith",
            date="2025-05-10",
            age_days=4,
            file_modifications=2,
            priority_score=0.15,
            priority_bucket="low",
        ),
    ]
    
    console.print("[bold]Testing reporter with sample data...[/bold]\n")
    print_report(test_markers, scan_path="./sample_project")
