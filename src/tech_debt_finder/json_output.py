"""
json_output.py - JSON serialization for snapshots

Snapshots allow you to:
1. Save scan results to a file
2. Compare scans over time (trend tracking)
3. Integrate with CI/CD pipelines

JSON SCHEMA
===========
{
    "version": "1.0",
    "scan_date": "2025-05-15T10:30:00Z",
    "scan_path": "/path/to/repo",
    "total_markers": 47,
    "by_priority": {"high": 8, "medium": 22, "low": 17},
    "by_type": {"TODO": 31, "FIXME": 9, "HACK": 5, "TEMP": 2},
    "markers": [
        {
            "fingerprint": "a1b2c3d4e5f6",
            "file": "src/auth.dart",
            "line": 142,
            "marker_type": "TODO",
            "text": "handle token refresh",
            "author": "alice",
            "date": "2024-03-15",
            "age_days": 426,
            "file_modifications": 34,
            "priority_score": 0.92,
            "priority_bucket": "high"
        }
    ]
}

FINGERPRINTING
==============
Each marker gets a fingerprint based on:
- file path
- marker type
- text content

This allows tracking the SAME marker across scans even if line numbers change.
"""

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_debt_finder.scanner import Marker, count_by_type
from tech_debt_finder.prioritizer import group_by_priority


# Schema version - increment when format changes
SCHEMA_VERSION = "1.0"


def generate_fingerprint(marker: Marker) -> str:
    """
    Generate a stable fingerprint for a marker.
    
    The fingerprint is based on file + type + text, so it survives
    line number changes during refactoring.
    
    Args:
        marker: A Marker object
        
    Returns:
        12-character hex string
    """
    # Normalize the inputs
    content = f"{marker.file}:{marker.marker_type}:{marker.text}"
    
    # Create MD5 hash and take first 12 characters
    # MD5 is fine here - we're not doing security, just deduplication
    hash_obj = hashlib.md5(content.encode("utf-8"))
    return hash_obj.hexdigest()[:12]


def marker_to_dict(marker: Marker) -> dict[str, Any]:
    """
    Convert a Marker to a JSON-serializable dictionary.
    """
    return {
        "fingerprint": generate_fingerprint(marker),
        "file": marker.file,
        "line": marker.line,
        "marker_type": marker.marker_type,
        "text": marker.text,
        "full_line": marker.full_line,
        "author": marker.author,
        "date": marker.date,
        "age_days": marker.age_days,
        "file_modifications": marker.file_modifications,
        "priority_score": round(marker.priority_score, 3),
        "priority_bucket": marker.priority_bucket,
    }


def create_snapshot(markers: list[Marker], scan_path: str) -> dict[str, Any]:
    """
    Create a snapshot dictionary from scan results.
    
    Args:
        markers: List of prioritized markers
        scan_path: Path that was scanned
        
    Returns:
        Dictionary ready for JSON serialization
    """
    # Group counts
    groups = group_by_priority(markers)
    type_counts = count_by_type(markers)
    
    return {
        "version": SCHEMA_VERSION,
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "scan_path": str(Path(scan_path).resolve()),
        "total_markers": len(markers),
        "by_priority": {
            "high": len(groups["high"]),
            "medium": len(groups["medium"]),
            "low": len(groups["low"]),
        },
        "by_type": type_counts,
        "markers": [marker_to_dict(m) for m in markers],
    }


def snapshot_to_json(markers: list[Marker], scan_path: str, pretty: bool = True) -> str:
    """
    Convert scan results to JSON string.
    
    Args:
        markers: List of prioritized markers
        scan_path: Path that was scanned
        pretty: If True, format with indentation
        
    Returns:
        JSON string
    """
    snapshot = create_snapshot(markers, scan_path)
    
    if pretty:
        return json.dumps(snapshot, indent=2, ensure_ascii=False)
    else:
        return json.dumps(snapshot, ensure_ascii=False)


def save_snapshot(markers: list[Marker], scan_path: str, output_path: str) -> None:
    """
    Save scan results to a JSON file.
    
    Args:
        markers: List of prioritized markers
        scan_path: Path that was scanned
        output_path: Where to save the JSON file
    """
    json_str = snapshot_to_json(markers, scan_path, pretty=True)
    Path(output_path).write_text(json_str, encoding="utf-8")


def load_snapshot(file_path: str) -> dict[str, Any]:
    """
    Load a snapshot from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Snapshot dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    content = Path(file_path).read_text(encoding="utf-8")
    return json.loads(content)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    from rich.console import Console
    from rich.syntax import Syntax
    
    console = Console()
    
    # Create sample markers
    test_markers = [
        Marker(
            file="src/auth_service.dart",
            line=142,
            marker_type="TODO",
            text="handle token refresh",
            full_line="// TODO: handle token refresh",
            author="alice",
            date="2024-03-15",
            age_days=426,
            file_modifications=34,
            priority_score=0.92,
            priority_bucket="high",
        ),
        Marker(
            file="src/profile_api.dart",
            line=89,
            marker_type="FIXME",
            text="breaks if null",
            full_line="// FIXME: breaks if null",
            author="bob",
            date="2024-01-22",
            age_days=478,
            file_modifications=28,
            priority_score=0.85,
            priority_bucket="high",
        ),
    ]
    
    console.print("[bold]Testing JSON output...[/bold]\n")
    
    # Generate JSON
    json_output = snapshot_to_json(test_markers, "./test_project")
    
    # Display with syntax highlighting
    syntax = Syntax(json_output, "json", theme="monokai", line_numbers=True)
    console.print(syntax)
    
    # Show fingerprints
    console.print("\n[bold]Fingerprints:[/bold]")
    for m in test_markers:
        console.print(f"  {generate_fingerprint(m)} → {m.file}:{m.line}")
