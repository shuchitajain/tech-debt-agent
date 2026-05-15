"""
server.py — MCP (Model Context Protocol) server

Exposes tech-debt-finder's core functions as tools callable by AI agents
(GitHub Copilot agent mode, Claude Desktop, Cursor, etc.).

This is the "agentic ways of working" surface: instead of running CLI commands,
a developer asks Copilot "what's the worst tech debt in this repo?" and Copilot
invokes the scan_repo tool here, gets structured JSON back, and reasons about it.

WHY MCP?
========
MCP is Anthropic's open standard for plugging tools into LLM agents. Any MCP-aware
client (Copilot, Claude, Cursor) can discover and call these tools with no
custom integration code on the client side.

ARCHITECTURE
============
- Each @mcp.tool() function = one tool the LLM can call.
- Returns must be JSON-serializable (dict, list, str, int, float, bool).
- We wrap existing pure functions; no business logic lives here.

TRANSPORT
=========
stdio (standard input/output). VS Code launches the server as a subprocess,
exchanges JSON-RPC messages over stdin/stdout. Configured via .vscode/mcp.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from tech_debt_finder.scanner import scan_directory
from tech_debt_finder.git_utils import enrich_markers
from tech_debt_finder.prioritizer import prioritize_markers, group_by_priority
from tech_debt_finder.json_output import (
    marker_to_dict,
    create_snapshot,
    save_snapshot,
    load_snapshot,
)
from tech_debt_finder.trend import compare_snapshots


mcp = FastMCP("tech-debt-finder")


# =============================================================================
# Internal helpers
# =============================================================================

def _scan_and_prioritize(path: str, age_days: int = 0) -> list:
    """Run the full scan pipeline and return prioritized markers."""
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"Path does not exist: {root}")

    markers = scan_directory(root)
    markers = enrich_markers(markers)
    markers = prioritize_markers(markers)

    if age_days > 0:
        markers = [m for m in markers if m.age_days >= age_days]

    return markers


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
def scan_repo(path: str, age_days: int = 0) -> dict[str, Any]:
    """
    Scan a repository for tech debt markers (TODO, FIXME, HACK, TEMP, XXX).

    Each marker is enriched with git blame data (author, age, file activity)
    and assigned a priority score and bucket (high/medium/low).

    Args:
        path: Absolute or ~-prefixed path to the repository or directory to scan.
        age_days: Optional minimum age in days. Markers younger than this are
                  filtered out. Default 0 (no filter).

    Returns:
        Dict with keys:
        - scan_path: resolved absolute path scanned
        - total_markers: int
        - by_priority: {high, medium, low} counts
        - by_type: {TODO, FIXME, ...} counts
        - markers: list of marker dicts (file, line, type, text, author,
                   age_days, file_modifications, priority_score, priority_bucket)
    """
    markers = _scan_and_prioritize(path, age_days)
    return create_snapshot(markers, str(Path(path).expanduser().resolve()))


@mcp.tool()
def get_top_priorities(path: str, limit: int = 10) -> dict[str, Any]:
    """
    Get the top N highest-priority tech debt items in a repository.

    Use this when you want to answer "what should I fix first?" without
    pulling back every marker. Results are sorted by priority_score descending.

    Args:
        path: Absolute or ~-prefixed path to the repository to scan.
        limit: Maximum number of markers to return. Default 10.

    Returns:
        Dict with keys:
        - scan_path: resolved absolute path scanned
        - total_markers: total found (before limit)
        - returned: how many markers in the response
        - markers: list of top-N marker dicts, highest priority first
    """
    markers = _scan_and_prioritize(path)
    top = markers[:limit]
    return {
        "scan_path": str(Path(path).expanduser().resolve()),
        "total_markers": len(markers),
        "returned": len(top),
        "markers": [marker_to_dict(m) for m in top],
    }


@mcp.tool()
def save_tech_debt_snapshot(path: str, output_path: str) -> dict[str, Any]:
    """
    Scan a repository and save the results as a JSON snapshot file.

    Snapshots are used for trend tracking — compare two snapshots taken at
    different times to see what's been resolved vs added.

    Args:
        path: Absolute or ~-prefixed path to the repository to scan.
        output_path: Where to write the snapshot JSON file.

    Returns:
        Dict with keys:
        - output_path: resolved path where snapshot was written
        - total_markers: int
        - by_priority: {high, medium, low} counts
    """
    markers = _scan_and_prioritize(path)
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    save_snapshot(markers, str(Path(path).expanduser().resolve()), str(out))

    groups = group_by_priority(markers)
    return {
        "output_path": str(out),
        "total_markers": len(markers),
        "by_priority": {
            "high": len(groups["high"]),
            "medium": len(groups["medium"]),
            "low": len(groups["low"]),
        },
    }


@mcp.tool()
def compare_tech_debt_snapshots(old_path: str, new_path: str) -> dict[str, Any]:
    """
    Compare two tech debt snapshot files to see what changed.

    Markers are matched across snapshots by fingerprint (file + type + text),
    so they survive line-number changes from refactoring.

    Args:
        old_path: Path to the earlier snapshot JSON file.
        new_path: Path to the later snapshot JSON file.

    Returns:
        Dict with keys:
        - old_date, new_date: ISO timestamps of each snapshot
        - old_total, new_total: marker counts
        - resolved_count: markers in old but not new
        - added_count: markers in new but not old
        - net_change: new_total - old_total (negative = improving)
        - is_improving: bool
        - completion_rate: % of old markers resolved
        - old_by_priority, new_by_priority: priority breakdowns
        - resolved_markers, added_markers: full marker dicts for each
    """
    old_snap = load_snapshot(str(Path(old_path).expanduser().resolve()))
    new_snap = load_snapshot(str(Path(new_path).expanduser().resolve()))
    report = compare_snapshots(old_snap, new_snap)

    return {
        "old_date": report.old_date,
        "new_date": report.new_date,
        "old_path": report.old_path,
        "new_path": report.new_path,
        "old_total": report.old_total,
        "new_total": report.new_total,
        "resolved_count": report.resolved_count,
        "added_count": report.added_count,
        "net_change": report.net_change,
        "is_improving": report.is_improving,
        "completion_rate": round(report.completion_rate, 1),
        "old_by_priority": report.old_by_priority,
        "new_by_priority": report.new_by_priority,
        "old_by_type": report.old_by_type,
        "new_by_type": report.new_by_type,
        "resolved_markers": report.resolved_markers,
        "added_markers": report.added_markers,
    }


@mcp.tool()
def explain_marker(path: str, file: str, line: int) -> dict[str, Any]:
    """
    Get full details on a single tech debt marker by file and line number.

    Useful when a developer asks "tell me about the TODO on line 142 of auth.dart" —
    returns the marker's text, author, age, priority score, and reasoning context
    (file modification count, priority bucket).

    Args:
        path: Absolute or ~-prefixed path to the repository.
        file: Relative path of the file containing the marker (e.g. "lib/main.dart")
              OR absolute path. Matched against marker.file.
        line: Line number of the marker (1-indexed).

    Returns:
        Dict with the marker details, or {"found": false, "reason": ...} if no
        marker exists at that location.
    """
    markers = _scan_and_prioritize(path)

    # Normalize search file to handle both relative and absolute matches
    file_norm = file.replace("\\", "/")
    file_basename = Path(file_norm).name

    for m in markers:
        m_file = m.file.replace("\\", "/")
        # Match if file path ends with the requested file, or exact basename match
        if m.line == line and (m_file.endswith(file_norm) or Path(m_file).name == file_basename):
            d = marker_to_dict(m)
            d["found"] = True
            return d

    return {
        "found": False,
        "reason": f"No marker found at {file}:{line}",
        "scanned_path": str(Path(path).expanduser().resolve()),
    }


# =============================================================================
# Entry point
# =============================================================================

def main() -> None:
    """Launch the MCP server over stdio. Called by the `tech-debt-mcp` script."""
    mcp.run()


if __name__ == "__main__":
    main()
