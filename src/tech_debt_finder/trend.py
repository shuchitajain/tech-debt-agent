"""
trend.py - Compare snapshots to track tech debt over time

This module answers questions like:
- How many TODOs did we fix this sprint?
- How many new TODOs were added?
- Is our tech debt getting better or worse?

COMPARISON LOGIC
================
We use fingerprints (not line numbers) to match markers across snapshots.
This means we can detect:

- RESOLVED: marker in old snapshot but not in new
- NEW: marker in new snapshot but not in old
- STILL EXISTS: marker in both snapshots

A marker is "the same" if its fingerprint matches (file + type + text).
"""

from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from tech_debt_finder.json_output import load_snapshot


@dataclass
class TrendReport:
    """Results of comparing two snapshots."""
    
    # Counts
    old_total: int
    new_total: int
    resolved_count: int
    added_count: int
    
    # Priority breakdowns
    old_by_priority: dict[str, int]
    new_by_priority: dict[str, int]
    
    # Type breakdowns
    old_by_type: dict[str, int]
    new_by_type: dict[str, int]
    
    # Details
    resolved_markers: list[dict]
    added_markers: list[dict]
    
    # Metadata
    old_date: str
    new_date: str
    old_path: str
    new_path: str
    
    @property
    def net_change(self) -> int:
        """Positive = more debt, negative = less debt."""
        return self.new_total - self.old_total
    
    @property
    def is_improving(self) -> bool:
        """True if we're reducing tech debt."""
        return self.net_change < 0
    
    @property
    def completion_rate(self) -> float:
        """Percentage of old markers that were resolved."""
        if self.old_total == 0:
            return 0.0
        return (self.resolved_count / self.old_total) * 100


def compare_snapshots(old_snapshot: dict, new_snapshot: dict) -> TrendReport:
    """
    Compare two snapshots and generate a trend report.
    
    Args:
        old_snapshot: Earlier snapshot (dict from load_snapshot)
        new_snapshot: Later snapshot (dict from load_snapshot)
        
    Returns:
        TrendReport with comparison results
    """
    # Extract markers and create fingerprint sets
    old_markers = {m["fingerprint"]: m for m in old_snapshot.get("markers", [])}
    new_markers = {m["fingerprint"]: m for m in new_snapshot.get("markers", [])}
    
    old_fingerprints = set(old_markers.keys())
    new_fingerprints = set(new_markers.keys())
    
    # Find resolved (in old but not in new)
    resolved_fps = old_fingerprints - new_fingerprints
    resolved_markers = [old_markers[fp] for fp in resolved_fps]
    
    # Find added (in new but not in old)
    added_fps = new_fingerprints - old_fingerprints
    added_markers = [new_markers[fp] for fp in added_fps]
    
    return TrendReport(
        old_total=old_snapshot.get("total_markers", 0),
        new_total=new_snapshot.get("total_markers", 0),
        resolved_count=len(resolved_markers),
        added_count=len(added_markers),
        old_by_priority=old_snapshot.get("by_priority", {}),
        new_by_priority=new_snapshot.get("by_priority", {}),
        old_by_type=old_snapshot.get("by_type", {}),
        new_by_type=new_snapshot.get("by_type", {}),
        resolved_markers=resolved_markers,
        added_markers=added_markers,
        old_date=old_snapshot.get("scan_date", "unknown"),
        new_date=new_snapshot.get("scan_date", "unknown"),
        old_path=old_snapshot.get("scan_path", "unknown"),
        new_path=new_snapshot.get("scan_path", "unknown"),
    )


def compare_snapshot_files(old_path: str, new_path: str) -> TrendReport:
    """
    Compare two snapshot files.
    
    Args:
        old_path: Path to older snapshot JSON
        new_path: Path to newer snapshot JSON
        
    Returns:
        TrendReport with comparison results
    """
    old_snapshot = load_snapshot(old_path)
    new_snapshot = load_snapshot(new_path)
    return compare_snapshots(old_snapshot, new_snapshot)


# =============================================================================
# REPORTING
# =============================================================================

def print_trend_report(report: TrendReport) -> None:
    """Print a formatted trend report to the terminal."""
    console = Console()
    
    # Header
    console.print("\n[bold blue]📈 Tech Debt Trend Report[/bold blue]")
    console.print(f"[dim]Comparing: {report.old_date[:10]} → {report.new_date[:10]}[/dim]\n")
    
    # Summary panel
    if report.is_improving:
        trend_icon = "✅"
        trend_color = "green"
        trend_text = f"Improving! Net reduction of {abs(report.net_change)} markers."
    elif report.net_change == 0:
        trend_icon = "➡️"
        trend_color = "yellow"
        trend_text = "No change in total markers."
    else:
        trend_icon = "⚠️"
        trend_color = "red"
        trend_text = f"Getting worse. Net increase of {report.net_change} markers."
    
    summary_lines = [
        f"[bold]Total markers:[/bold] {report.old_total} → {report.new_total}",
        f"[green]Resolved:[/green] {report.resolved_count}",
        f"[red]Added:[/red] {report.added_count}",
        f"[bold]Net change:[/bold] {report.net_change:+d}",
        "",
        f"[{trend_color}]{trend_icon} {trend_text}[/{trend_color}]",
    ]
    
    panel = Panel(
        "\n".join(summary_lines),
        title="Summary",
        border_style=trend_color,
    )
    console.print(panel)
    
    # Priority breakdown
    console.print("\n[bold]By Priority:[/bold]")
    priority_table = Table(show_header=True)
    priority_table.add_column("Priority")
    priority_table.add_column("Before", justify="right")
    priority_table.add_column("After", justify="right")
    priority_table.add_column("Change", justify="right")
    
    for priority in ["high", "medium", "low"]:
        old_count = report.old_by_priority.get(priority, 0)
        new_count = report.new_by_priority.get(priority, 0)
        change = new_count - old_count
        change_str = f"{change:+d}" if change != 0 else "-"
        change_style = "red" if change > 0 else "green" if change < 0 else "dim"
        
        priority_color = {"high": "red", "medium": "yellow", "low": "green"}[priority]
        
        priority_table.add_row(
            f"[{priority_color}]{priority.upper()}[/{priority_color}]",
            str(old_count),
            str(new_count),
            f"[{change_style}]{change_str}[/{change_style}]",
        )
    
    console.print(priority_table)
    
    # Resolved markers (top 5)
    if report.resolved_markers:
        console.print(f"\n[bold green]✅ Resolved ({report.resolved_count}):[/bold green]")
        for m in report.resolved_markers[:5]:
            console.print(f"  [dim]{m['file']}:{m['line']}[/dim] - {m['text'][:50]}")
        if len(report.resolved_markers) > 5:
            console.print(f"  [dim]... and {len(report.resolved_markers) - 5} more[/dim]")
    
    # Added markers (top 5)
    if report.added_markers:
        console.print(f"\n[bold red]🆕 Added ({report.added_count}):[/bold red]")
        for m in report.added_markers[:5]:
            console.print(f"  [dim]{m['file']}:{m['line']}[/dim] - {m['text'][:50]}")
        if len(report.added_markers) > 5:
            console.print(f"  [dim]... and {len(report.added_markers) - 5} more[/dim]")
    
    console.print()


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    console = Console()
    
    console.print("[bold]Testing trend comparison...[/bold]\n")
    
    # Create fake old snapshot
    old_snapshot = {
        "version": "1.0",
        "scan_date": "2025-05-01T10:00:00Z",
        "scan_path": "/test/repo",
        "total_markers": 47,
        "by_priority": {"high": 8, "medium": 22, "low": 17},
        "by_type": {"TODO": 31, "FIXME": 9, "HACK": 5, "TEMP": 2},
        "markers": [
            {"fingerprint": "aaa111", "file": "auth.dart", "line": 10, "text": "fix auth"},
            {"fingerprint": "bbb222", "file": "api.dart", "line": 20, "text": "handle null"},
            {"fingerprint": "ccc333", "file": "utils.dart", "line": 30, "text": "refactor this"},
        ]
    }
    
    # Create fake new snapshot (one resolved, one added)
    new_snapshot = {
        "version": "1.0",
        "scan_date": "2025-05-15T10:00:00Z",
        "scan_path": "/test/repo",
        "total_markers": 45,
        "by_priority": {"high": 5, "medium": 22, "low": 18},
        "by_type": {"TODO": 29, "FIXME": 9, "HACK": 5, "TEMP": 2},
        "markers": [
            {"fingerprint": "aaa111", "file": "auth.dart", "line": 10, "text": "fix auth"},  # Still exists
            # bbb222 is gone (resolved!)
            {"fingerprint": "ccc333", "file": "utils.dart", "line": 30, "text": "refactor this"},  # Still exists
            {"fingerprint": "ddd444", "file": "new.dart", "line": 5, "text": "new todo"},  # New!
        ]
    }
    
    # Compare
    report = compare_snapshots(old_snapshot, new_snapshot)
    print_trend_report(report)
