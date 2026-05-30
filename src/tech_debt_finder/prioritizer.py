"""
prioritizer.py - Calculate priority scores for markers

The scoring formula:
    score = (age_score × 0.6) + (activity_score × 0.4)

Where:
- age_score: How old is this TODO? (logarithmic scale, capped at 2 years)
- activity_score: How often is this file modified? (linear, capped at 50 mods)

WHY THIS FORMULA?
=================
Age alone isn't enough. Consider:
- A 2-year-old TODO in a dead file → Low priority (nobody touches it)
- A 2-year-old TODO in an active file → HIGH priority (people keep ignoring it!)

The activity component captures "this code gets attention, but this TODO doesn't."

WHY LOGARITHMIC?
================
Raw age creates huge differences:
- 730 days vs 30 days = 24x difference

But intuitively, a 2-year-old TODO isn't 24x more urgent than a 1-month-old one.
Using log() compresses this:
- log(730) vs log(30) = ~2x difference

This feels more proportional to human judgment.

PRIORITY BUCKETS
================
After scoring, we bucket into human-readable categories:
- HIGH:   score > 0.6 → Fix soon, this is hurting you
- MEDIUM: score > 0.3 → Should address, but not urgent
- LOW:    score ≤ 0.3 → Nice to have, low impact
"""

import math
from tech_debt_finder.scanner import Marker


# =============================================================================
# CONFIGURATION - Tune these to change behavior
# =============================================================================

# Maximum age we consider (anything older gets same score)
# 730 days = 2 years
MAX_AGE_DAYS = 730

# Maximum file modifications we consider
# 50+ mods = very active file
MAX_FILE_MODIFICATIONS = 50

# How much weight to give each factor (must sum to 1.0)
AGE_WEIGHT = 0.6
ACTIVITY_WEIGHT = 0.4

# Score thresholds for priority buckets
HIGH_THRESHOLD = 0.6
MEDIUM_THRESHOLD = 0.3


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def calculate_age_score(age_days: int) -> float:
    """
    Calculate a score from 0.0 to 1.0 based on age.
    
    Uses logarithmic scaling so:
    - 0 days → 0.0
    - ~90 days → 0.5
    - 730 days (2 years) → 1.0
    
    Args:
        age_days: Number of days since the marker was added
        
    Returns:
        Float from 0.0 to 1.0
        
    Examples:
        calculate_age_score(0)    → 0.0
        calculate_age_score(90)   → ~0.5
        calculate_age_score(730)  → 1.0
        calculate_age_score(1000) → 1.0 (capped)
    """
    if age_days <= 0:
        return 0.0
    
    # Add 1 to avoid log(0) which is undefined
    # log(age + 1) / log(max_age + 1) normalizes to 0-1 range
    #
    # Why log(MAX_AGE_DAYS + 1) as denominator?
    # It makes the score exactly 1.0 when age = MAX_AGE_DAYS
    
    score = math.log(age_days + 1) / math.log(MAX_AGE_DAYS + 1)
    
    # Cap at 1.0 (anything older than MAX_AGE_DAYS gets same score)
    return min(score, 1.0)


def calculate_activity_score(file_modifications: int) -> float:
    """
    Calculate a score from 0.0 to 1.0 based on file activity.
    
    Uses linear scaling:
    - 0 mods → 0.0
    - 25 mods → 0.5
    - 50+ mods → 1.0
    
    Args:
        file_modifications: Number of commits that touched this file
                           since the marker was added
        
    Returns:
        Float from 0.0 to 1.0
    """
    if file_modifications <= 0:
        return 0.0
    
    # Simple linear scale, capped at MAX_FILE_MODIFICATIONS
    score = file_modifications / MAX_FILE_MODIFICATIONS
    
    return min(score, 1.0)


def calculate_priority_score(marker: Marker) -> float:
    """
    Calculate the overall priority score for a marker.
    
    Formula: score = (age_score × 0.6) + (activity_score × 0.4)
    
    Args:
        marker: A Marker object with age_days and file_modifications set
        
    Returns:
        Float from 0.0 to 1.0
    """
    age_score = calculate_age_score(marker.age_days)
    activity_score = calculate_activity_score(marker.file_modifications)
    
    # Weighted combination
    return (age_score * AGE_WEIGHT) + (activity_score * ACTIVITY_WEIGHT)


def get_priority_bucket(score: float) -> str:
    """
    Convert a numeric score into a human-readable priority.
    
    Args:
        score: Float from 0.0 to 1.0
        
    Returns:
        "high", "medium", or "low"
    """
    if score > HIGH_THRESHOLD:
        return "high"
    elif score > MEDIUM_THRESHOLD:
        return "medium"
    else:
        return "low"


# =============================================================================
# MAIN FUNCTION - Prioritize markers
# =============================================================================

def prioritize_marker(marker: Marker) -> Marker:
    """
    Calculate and set priority for a single marker.
    
    Modifies the marker in place and also returns it.
    
    Args:
        marker: A Marker with git info already filled in
        
    Returns:
        The same marker with priority_score and priority_bucket set
    """
    marker.priority_score = calculate_priority_score(marker)
    marker.priority_bucket = get_priority_bucket(marker.priority_score)
    return marker


def prioritize_markers(markers: list[Marker]) -> list[Marker]:
    """
    Calculate priorities for all markers and sort by priority.
    
    Args:
        markers: List of Marker objects with git info filled in
        
    Returns:
        Same list, sorted by priority (highest first)
    """
    for marker in markers:
        prioritize_marker(marker)
    
    # Sort by priority score, highest first
    # In Python, sorted() returns a new list
    # key=lambda m: m.priority_score tells it what to sort by
    # reverse=True means descending order (highest first)
    return sorted(markers, key=lambda m: m.priority_score, reverse=True)


def group_by_priority(markers: list[Marker]) -> dict[str, list[Marker]]:
    """
    Group markers by priority bucket.
    
    Args:
        markers: List of prioritized markers
        
    Returns:
        Dict like {'high': [...], 'medium': [...], 'low': [...]}
    """
    groups: dict[str, list[Marker]] = {
        "high": [],
        "medium": [],
        "low": [],
    }
    
    for marker in markers:
        bucket = marker.priority_bucket
        groups[bucket].append(marker)
    
    return groups


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    console.print("[bold]Testing prioritizer with sample data...[/]\n")
    
    # Create some fake markers to demonstrate the scoring
    test_cases = [
        ("A: Old + Active", 730, 40),      # 2 years old, 40 mods → HIGH
        ("B: Old + Dead file", 730, 0),    # 2 years old, 0 mods → Medium
        ("C: New + Active", 7, 50),         # 1 week old, 50 mods → Medium
        ("D: New + Dead", 7, 0),            # 1 week old, 0 mods → LOW
        ("E: Medium age + Medium activity", 90, 25),  # ~3 months, 25 mods
        ("F: Very old + Some activity", 1000, 20),    # Capped age
    ]
    
    table = Table(title="Priority Scoring Examples")
    table.add_column("Scenario", style="white")
    table.add_column("Age (days)", justify="right")
    table.add_column("File Mods", justify="right")
    table.add_column("Age Score", justify="right", style="cyan")
    table.add_column("Activity Score", justify="right", style="cyan")
    table.add_column("Final Score", justify="right", style="yellow")
    table.add_column("Priority", style="bold")
    
    for name, age_days, file_mods in test_cases:
        # Create a fake marker
        marker = Marker(
            file="test.py",
            line=1,
            marker_type="TODO",
            text="test",
            full_line="# TODO: test",
            age_days=age_days,
            file_modifications=file_mods,
        )
        
        # Calculate scores
        age_score = calculate_age_score(age_days)
        activity_score = calculate_activity_score(file_mods)
        prioritize_marker(marker)
        
        # Color the priority
        priority_color = {
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }[marker.priority_bucket]
        
        table.add_row(
            name,
            str(age_days),
            str(file_mods),
            f"{age_score:.2f}",
            f"{activity_score:.2f}",
            f"{marker.priority_score:.2f}",
            f"[{priority_color}]{marker.priority_bucket.upper()}[/{priority_color}]",
        )
    
    console.print(table)
    
    console.print("\n[bold]Formula:[/]")
    console.print(f"  score = (age_score × {AGE_WEIGHT}) + (activity_score × {ACTIVITY_WEIGHT})")
    console.print(f"\n[bold]Thresholds:[/]")
    console.print(f"  HIGH:   score > {HIGH_THRESHOLD}")
    console.print(f"  MEDIUM: score > {MEDIUM_THRESHOLD}")
    console.print(f"  LOW:    score ≤ {MEDIUM_THRESHOLD}")
