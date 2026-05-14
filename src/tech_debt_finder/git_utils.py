"""
git_utils.py — Get git information for TODO markers

This module uses git commands to find out:
1. WHO added a TODO (author)
2. WHEN it was added (date)
3. HOW ACTIVE is the file (modification count)

KEY CONCEPT: subprocess
=========================
Python can run any terminal command using the 'subprocess' module.
It's like running commands in your terminal, but from Python.

Dart equivalent: Process.run()

    # Dart
    final result = await Process.run('git', ['status']);
    print(result.stdout);
    
    # Python
    result = subprocess.run(['git', 'status'], capture_output=True, text=True)
    print(result.stdout)

The subprocess.run() function:
- Takes a LIST of command parts: ['git', 'blame', '-L', '12,12', 'file.py']
  (NOT a single string — this avoids shell injection security issues)
- capture_output=True → capture stdout and stderr
- text=True → return strings instead of bytes
- cwd=... → run in a specific directory

Returns a CompletedProcess object with:
- result.stdout → command output
- result.stderr → error output
- result.returncode → 0 means success, non-zero means error
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tech_debt_finder.scanner import Marker, iter_code_files


@dataclass
class DormantFile:
    """A file that hasn't been modified in a long time."""
    file: str
    days_since_modified: int
    last_modified_date: str
    last_author: str = "unknown"


# =============================================================================
# GIT BLAME — Who wrote this line and when?
# =============================================================================

def get_blame_info(file_path: str, line_number: int) -> dict:
    """
    Get git blame information for a specific line.
    
    Args:
        file_path: Path to the file
        line_number: Line number (1-indexed)
        
    Returns:
        Dict with 'author', 'date', 'age_days' keys
        Returns defaults if git blame fails
        
    Example:
        info = get_blame_info("src/auth.dart", 142)
        # {'author': 'alice', 'date': '2024-03-15', 'age_days': 426}
    """
    # Default values if git blame fails
    defaults = {
        "author": "unknown",
        "date": "unknown", 
        "age_days": 0,
    }
    
    try:
        # Run: git blame -L 142,142 --porcelain src/auth.dart
        #
        # -L 142,142 means "only line 142 to 142" (single line)
        # --porcelain means "output in a machine-readable format"
        #
        # Why porcelain? Regular git blame output is meant for humans.
        # Porcelain format is structured and easier to parse.
        
        result = subprocess.run(
            [
                "git", "blame",
                "-L", f"{line_number},{line_number}",  # Only this line
                "--porcelain",                          # Machine-readable format
                file_path
            ],
            capture_output=True,  # Capture stdout and stderr
            text=True,            # Return strings, not bytes
            timeout=10,           # Don't hang forever
        )
        
        # Check if command failed
        if result.returncode != 0:
            # Common reasons: file not in git, line doesn't exist
            return defaults
        
        # Parse the porcelain output
        # Format looks like:
        #   a1b2c3d4... 142 142 1
        #   author Alice Smith
        #   author-mail <alice@example.com>
        #   author-time 1710500000
        #   author-tz +0000
        #   ... more fields ...
        #   	// FIXME: actual line content
        
        author = "unknown"
        author_time = None
        
        for line in result.stdout.splitlines():
            if line.startswith("author "):
                # "author Alice Smith" → "Alice Smith"
                author = line[7:].strip()
            elif line.startswith("author-time "):
                # "author-time 1710500000" → 1710500000 (Unix timestamp)
                try:
                    author_time = int(line[12:].strip())
                except ValueError:
                    pass
        
        # Calculate age in days
        age_days = 0
        date_str = "unknown"
        
        if author_time:
            # Convert Unix timestamp to datetime
            blame_date = datetime.fromtimestamp(author_time, tz=timezone.utc)
            date_str = blame_date.strftime("%Y-%m-%d")
            
            # Calculate days since then
            now = datetime.now(tz=timezone.utc)
            age_days = (now - blame_date).days
        
        return {
            "author": author,
            "date": date_str,
            "age_days": age_days,
        }
        
    except subprocess.TimeoutExpired:
        # Command took too long
        return defaults
    except Exception as e:
        # Any other error (git not installed, not a repo, etc.)
        return defaults


# =============================================================================
# GIT LOG — How many times has this file been modified?
# =============================================================================

def get_file_modification_count(file_path: str, since_date: Optional[str] = None) -> int:
    """
    Count how many commits have modified this file.
    
    Args:
        file_path: Path to the file
        since_date: Optional date string (YYYY-MM-DD) to count from
        
    Returns:
        Number of commits that touched this file
        
    Example:
        count = get_file_modification_count("src/auth.dart")
        # 34 (this file has been modified 34 times)
        
        count = get_file_modification_count("src/auth.dart", "2024-03-15")
        # 12 (modified 12 times since March 15, 2024)
    """
    try:
        # Build the command
        # git log --oneline -- file.py
        # --oneline shows one line per commit (compact)
        # -- file.py means "only commits that touched this file"
        
        cmd = ["git", "log", "--oneline"]
        
        if since_date:
            # --since="2024-03-15" filters to commits after this date
            cmd.append(f"--since={since_date}")
        
        cmd.append("--")  # Separator between options and file path
        cmd.append(file_path)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode != 0:
            return 0
        
        # Count non-empty lines
        # Each line is one commit: "a1b2c3d Fix bug in auth"
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return len(lines)
        
    except Exception:
        return 0


def get_last_modified_date(file_path: str) -> Optional[str]:
    """
    Get the date of the most recent commit that touched this file.
    
    Returns:
        Date string (YYYY-MM-DD) or None if not in git
        
    Example:
        date = get_last_modified_date("src/auth.dart")
        # "2025-05-10"
    """
    try:
        # git log -1 --format=%ai -- file.py
        # -1 means "only the most recent commit"
        # --format=%ai means "output author date in ISO format"
        
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ai", "--", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return None
        
        # Output looks like: "2025-05-10 14:30:00 +0000"
        # We just want the date part
        date_part = result.stdout.strip().split()[0]
        return date_part
        
    except Exception:
        return None


# =============================================================================
# ENRICH MARKERS — Add git info to markers
# =============================================================================

def enrich_marker_with_git_info(marker: Marker) -> Marker:
    """
    Add git blame and log information to a marker.
    
    This modifies the marker in place (updates its fields).
    
    Args:
        marker: A Marker object from the scanner
        
    Returns:
        The same marker with git info filled in
    """
    # Get blame info (author, date, age)
    blame_info = get_blame_info(marker.file, marker.line)
    marker.author = blame_info["author"]
    marker.date = blame_info["date"]
    marker.age_days = blame_info["age_days"]
    
    # Get modification count since the TODO was added
    if blame_info["date"] != "unknown":
        marker.file_modifications = get_file_modification_count(
            marker.file, 
            since_date=blame_info["date"]
        )
    else:
        marker.file_modifications = get_file_modification_count(marker.file)
    
    return marker


def enrich_markers(markers: list[Marker]) -> list[Marker]:
    """
    Add git info to a list of markers.
    
    Args:
        markers: List of Marker objects
        
    Returns:
        Same list with git info added to each marker
    """
    for marker in markers:
        enrich_marker_with_git_info(marker)
    return markers


# =============================================================================
# DORMANT FILES — Files nobody has touched recently
# =============================================================================

def is_file_dormant(file_path: str, dormant_days: int = 180) -> bool:
    """
    Check if a file hasn't been modified in a long time.
    
    Args:
        file_path: Path to check
        dormant_days: Number of days without activity to consider "dormant"
        
    Returns:
        True if file hasn't been touched in dormant_days
    """
    last_modified = get_last_modified_date(file_path)
    
    if not last_modified:
        return False  # Not in git, can't tell
    
    try:
        last_date = datetime.strptime(last_modified, "%Y-%m-%d")
        last_date = last_date.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        days_since = (now - last_date).days
        return days_since >= dormant_days
    except ValueError:
        return False


def get_days_since_last_modified(file_path: str) -> int:
    """
    Get number of days since file was last modified.
    
    Returns 0 if file is not in git or can't be determined.
    """
    last_modified = get_last_modified_date(file_path)
    
    if not last_modified:
        return 0
    
    try:
        last_date = datetime.strptime(last_modified, "%Y-%m-%d")
        last_date = last_date.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        return (now - last_date).days
    except ValueError:
        return 0


def get_last_author(file_path: str) -> str:
    """Get the author of the most recent commit to this file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%an", "--", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def find_dormant_files(root: Path, dormant_days: int = 180) -> list[DormantFile]:
    """
    Find all files that haven't been modified in a long time.
    
    Args:
        root: Directory to scan
        dormant_days: Days without activity to consider "dormant"
        
    Returns:
        List of DormantFile objects, sorted by age (oldest first)
    """
    dormant = []
    
    for file_path in iter_code_files(root):
        days = get_days_since_last_modified(str(file_path))
        
        if days >= dormant_days:
            last_date = get_last_modified_date(str(file_path)) or "unknown"
            last_author = get_last_author(str(file_path))
            
            dormant.append(DormantFile(
                file=str(file_path),
                days_since_modified=days,
                last_modified_date=last_date,
                last_author=last_author,
            ))
    
    # Sort by days (oldest first)
    dormant.sort(key=lambda d: d.days_since_modified, reverse=True)
    return dormant


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    from tech_debt_finder.scanner import scan_directory
    
    console = Console()
    
    console.print("[bold]Testing git_utils...[/]\n")
    
    # First, check if we're in a git repo
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        console.print("[red]Not in a git repository! Initializing one for testing...[/]")
        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "add", "."], capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            capture_output=True,
            env={"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@test.com",
                 "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@test.com"}
        )
    
    # Scan for markers
    markers = scan_directory(Path("."))
    
    if not markers:
        console.print("[yellow]No markers found![/]")
    else:
        # Enrich with git info
        console.print(f"[dim]Enriching {len(markers)} markers with git info...[/]\n")
        enrich_markers(markers)
        
        # Show results
        table = Table(title="Markers with Git Info")
        table.add_column("Type", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Line", justify="right")
        table.add_column("Author", style="yellow")
        table.add_column("Age", justify="right")
        table.add_column("File Mods", justify="right")
        
        for m in markers[:10]:
            table.add_row(
                m.marker_type,
                Path(m.file).name,  # Just filename, not full path
                str(m.line),
                m.author[:15] if len(m.author) > 15 else m.author,
                f"{m.age_days}d",
                str(m.file_modifications),
            )
        
        console.print(table)
        
        if len(markers) > 10:
            console.print(f"\n[dim]... and {len(markers) - 10} more[/]")
