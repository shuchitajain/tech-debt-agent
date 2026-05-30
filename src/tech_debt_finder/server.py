"""
server.py - MCP (Model Context Protocol) server

Exposes tech-debt-agent's core functions as tools callable by AI agents
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

import json
import os
from pathlib import Path
from typing import Any

import requests
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


mcp = FastMCP("tech-debt-agent")


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

    Snapshots are used for trend tracking - compare two snapshots taken at
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

    Useful when a developer asks "tell me about the TODO on line 142 of auth.dart" -
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
# Agentic tools - mutation / triage surface
# =============================================================================

@mcp.tool()
def generate_triage_report(
    path: str,
    limit: int = 30,
    age_days: int = 0,
) -> dict[str, Any]:
    """
    Run the full scan+prioritize pipeline and return a structured triage report.

    This is the primary entry point for the tech-debt agent. Call this first
    to get a complete picture of the repo's tech debt before deciding which
    items to file as GitHub issues.

    Args:
        path: Absolute or ~-prefixed path to the repository to scan.
        limit: Maximum markers to include per priority bucket. Default 30.
        age_days: Minimum age filter in days. Default 0 (no filter).

    Returns:
        Dict with keys:
        - scan_path: resolved absolute path scanned
        - scan_date: ISO timestamp
        - total_markers: int
        - by_priority: {high, medium, low} with counts and marker lists
          Each marker includes: file, line, type, text, author, age_days,
          file_modifications, priority_score, priority_bucket, fingerprint
        - by_type: {TODO, FIXME, HACK, TEMP, XXX} counts
        - scoring_notes: explanation of the scoring formula for agent reasoning
    """
    markers = _scan_and_prioritize(path, age_days)
    groups = group_by_priority(markers)

    def _trim(bucket: list, n: int) -> list[dict]:
        return [marker_to_dict(m) for m in bucket[:n]]

    snapshot = create_snapshot(markers, str(Path(path).expanduser().resolve()))

    return {
        "scan_path": snapshot["scan_path"],
        "scan_date": snapshot["scan_date"],
        "total_markers": snapshot["total_markers"],
        "by_priority": {
            "high": {
                "count": len(groups["high"]),
                "markers": _trim(groups["high"], limit),
            },
            "medium": {
                "count": len(groups["medium"]),
                "markers": _trim(groups["medium"], limit),
            },
            "low": {
                "count": len(groups["low"]),
                "markers": _trim(groups["low"], limit),
            },
        },
        "by_type": snapshot["by_type"],
        "scoring_notes": (
            "score = log(age_days+1)/log(731) * 0.6 + min(file_modifications/50,1) * 0.4. "
            "HIGH > 0.6, MEDIUM > 0.3, LOW <= 0.3. "
            "Age is capped at 730 days (2 years). Activity is capped at 50 file modifications."
        ),
    }


@mcp.tool()
def check_existing_issue(repo: str, title: str) -> dict[str, Any]:
    """
    Check if a GitHub issue with the given title already exists.

    Call this before create_github_issue to avoid filing duplicates.
    Uses GitHub's search API with an exact title match.

    Args:
        repo: GitHub repo in "owner/repo" format (e.g. "shuchitajain/my-app").
        title: Exact issue title to search for.

    Returns:
        Dict with keys:
        - exists: bool
        - issue_url: URL of existing issue if found, else null
        - issue_number: int if found, else null
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"exists": False, "issue_url": None, "issue_number": None,
                "error": "GITHUB_TOKEN not set"}

    query = f'"{title}" in:title repo:{repo} is:issue'
    try:
        resp = requests.get(
            "https://api.github.com/search/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"q": query},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("total_count", 0) > 0:
                item = data["items"][0]
                return {
                    "exists": True,
                    "issue_url": item["html_url"],
                    "issue_number": item["number"],
                }
            return {"exists": False, "issue_url": None, "issue_number": None}
        return {"exists": False, "issue_url": None, "issue_number": None,
                "error": f"GitHub API returned {resp.status_code}"}
    except requests.exceptions.RequestException as exc:
        return {"exists": False, "issue_url": None, "issue_number": None,
                "error": str(exc)}


@mcp.tool()
def create_github_issue(
    repo: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a GitHub issue for a tech debt item.

    Always call check_existing_issue first to avoid duplicates.
    Requires the GITHUB_TOKEN environment variable to be set with
    repo (private) or public_repo (public) scope.

    Args:
        repo: GitHub repo in "owner/repo" format.
        title: Issue title. Convention: "[tech-debt] TYPE: file description"
        body: Issue body in Markdown. Include file, line, author, age, code context.
        labels: Optional list of label names (e.g. ["tech-debt", "high-priority"]).
                Labels must already exist in the repo.

    Returns:
        Dict with keys:
        - success: bool
        - issue_url: URL of the created issue (if success)
        - issue_number: int (if success)
        - error: error message (if not success)
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"success": False, "error": "GITHUB_TOKEN not set"}

    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    try:
        resp = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=payload,
            timeout=30,
        )
        if resp.status_code == 201:
            data = resp.json()
            return {
                "success": True,
                "issue_url": data["html_url"],
                "issue_number": data["number"],
            }
        error_msg = resp.json().get("message", resp.text)
        return {"success": False, "error": f"GitHub API error ({resp.status_code}): {error_msg}"}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": str(exc)}


@mcp.tool()
def mark_wontfix(
    repo_path: str,
    fingerprint: str,
    reason: str,
) -> dict[str, Any]:
    """
    Mark a tech debt marker as won't-fix to exclude it from future triage reports.

    Writes to <repo_path>/.tech-debt-wontfix.json. This file should be committed
    to the repo so the exclusion persists across runs and is shared with the team.

    Args:
        repo_path: Absolute path to the repository root.
        fingerprint: The marker's fingerprint (MD5 hash from the triage report).
        reason: Why this is being marked won't-fix (written to the file).

    Returns:
        Dict with keys:
        - success: bool
        - wontfix_path: path to the wontfix file
        - total_wontfix: total number of wontfix entries after this addition
    """
    wontfix_file = Path(repo_path).expanduser().resolve() / ".tech-debt-wontfix.json"

    existing: dict[str, Any] = {}
    if wontfix_file.exists():
        try:
            existing = json.loads(wontfix_file.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    from datetime import datetime, timezone
    existing[fingerprint] = {
        "reason": reason,
        "marked_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        wontfix_file.write_text(json.dumps(existing, indent=2))
        return {
            "success": True,
            "wontfix_path": str(wontfix_file),
            "total_wontfix": len(existing),
        }
    except OSError as exc:
        return {"success": False, "error": str(exc)}


# =============================================================================
# Entry point
# =============================================================================

def main() -> None:
    """Launch the MCP server over stdio. Called by the `tech-debt-mcp` script."""
    mcp.run()


if __name__ == "__main__":
    main()
