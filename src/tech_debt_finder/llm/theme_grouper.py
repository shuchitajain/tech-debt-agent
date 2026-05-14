"""
theme_grouper.py — Cluster similar TODOs using Gemini

WHY GROUP BY THEME?
===================
When you have 50+ TODOs, a flat list is overwhelming. Grouping reveals patterns:
- "12 TODOs about error handling" → maybe a refactor is needed
- "8 TODOs in the auth module" → that area needs attention
- "5 FIXME about null checks" → defensive coding debt

Gemini looks at the text + file paths and clusters them semantically.

OUTPUT FORMAT
=============
{
    "themes": [
        {
            "name": "Error Handling",
            "description": "Missing try-catch blocks and null checks",
            "fingerprints": ["aaa111", "bbb222", "ccc333"],
            "count": 3
        },
        ...
    ],
    "ungrouped": ["ddd444"]  # Couldn't fit into any theme
}
"""

import json
from dataclasses import dataclass
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tech_debt_finder.scanner import Marker
from tech_debt_finder.json_output import generate_fingerprint
from tech_debt_finder.llm.client import chat_completion, is_configured


@dataclass
class Theme:
    """A group of related TODOs."""
    name: str
    description: str
    fingerprints: list[str]
    count: int


@dataclass
class ThemeGroupingResult:
    """Result of theme analysis."""
    themes: list[Theme]
    ungrouped: list[str]  # Fingerprints that couldn't be grouped
    
    @property
    def theme_count(self) -> int:
        return len(self.themes)


# System prompt for theme grouping
SYSTEM_PROMPT = """You are a code analyst specializing in technical debt. Your task is to group similar TODO/FIXME markers into meaningful themes.

Guidelines:
1. Group by SEMANTIC similarity, not just keywords
2. Theme names should be actionable (e.g., "Error Handling Gaps" not just "Errors")
3. Each theme needs at least 2 markers (don't create single-marker themes)
4. If a marker doesn't fit anywhere, put its fingerprint in "ungrouped"
5. Aim for 3-7 themes total
6. Look at both the TODO text AND the file path for context

Output ONLY valid JSON, no markdown code blocks."""


def _build_user_prompt(markers: list[Marker]) -> str:
    """Build the user prompt with marker data."""
    # Create a simplified representation for the LLM
    marker_data = []
    for m in markers:
        marker_data.append({
            "fingerprint": generate_fingerprint(m),
            "file": m.file,
            "type": m.marker_type,
            "text": m.text,
            "age_days": m.age_days,
        })
    
    return f"""Analyze these {len(markers)} code markers and group them by theme.

MARKERS:
{json.dumps(marker_data, indent=2)}

Return JSON in this exact format:
{{
    "themes": [
        {{
            "name": "Theme Name",
            "description": "Why these are grouped together",
            "fingerprints": ["abc123", "def456"]
        }}
    ],
    "ungrouped": ["ghi789"]
}}

IMPORTANT: The fingerprints in your response must EXACTLY match the fingerprints I provided."""


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks and extra text."""
    import re
    
    text = text.strip()
    
    # Try to find JSON in code blocks first
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if code_block_match:
        return code_block_match.group(1).strip()
    
    # Try to find JSON object directly (starts with { ends with })
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json_match.group(0)
    
    return text


def _parse_response(response_text: str, markers: list[Marker]) -> ThemeGroupingResult:
    """Parse LLM's response into structured result."""
    text = _extract_json(response_text)
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # If parsing fails, return everything as ungrouped
        console = Console()
        console.print(f"[yellow]Warning: Could not parse LLM response: {e}[/yellow]")
        all_fps = [generate_fingerprint(m) for m in markers]
        return ThemeGroupingResult(themes=[], ungrouped=all_fps)
    
    # Build Theme objects
    themes = []
    for t in data.get("themes", []):
        themes.append(Theme(
            name=t.get("name", "Unnamed"),
            description=t.get("description", ""),
            fingerprints=t.get("fingerprints", []),
            count=len(t.get("fingerprints", [])),
        ))
    
    return ThemeGroupingResult(
        themes=themes,
        ungrouped=data.get("ungrouped", []),
    )


def group_by_theme(markers: list[Marker]) -> Optional[ThemeGroupingResult]:
    """
    Group markers by semantic theme using Gemini.
    
    Args:
        markers: List of Marker objects
        
    Returns:
        ThemeGroupingResult with themes and ungrouped markers,
        or None if LLM is not configured
    """
    if not is_configured():
        return None
    
    if len(markers) < 3:
        # Not enough markers to meaningfully group
        return None
    
    # Limit to 50 markers to control token usage
    markers_to_analyze = markers[:50]
    
    user_prompt = _build_user_prompt(markers_to_analyze)
    
    response = chat_completion(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=2048,
        temperature=0.2,  # Low temperature for consistent grouping
    )
    
    return _parse_response(response, markers_to_analyze)


def print_theme_report(result: ThemeGroupingResult, markers: list[Marker]) -> None:
    """Print a formatted theme report."""
    console = Console()
    
    # Create fingerprint -> marker lookup
    fp_to_marker = {generate_fingerprint(m): m for m in markers}
    
    console.print("\n[bold blue]🏷️  Theme Analysis[/bold blue]")
    console.print(f"[dim]Found {result.theme_count} themes across {len(markers)} markers[/dim]\n")
    
    for theme in result.themes:
        # Theme header
        console.print(f"[bold]{theme.name}[/bold] ({theme.count} markers)")
        console.print(f"[dim]{theme.description}[/dim]")
        
        # Show markers in this theme
        for fp in theme.fingerprints[:5]:  # Show first 5
            marker = fp_to_marker.get(fp)
            if marker:
                priority_color = {
                    "high": "red",
                    "medium": "yellow", 
                    "low": "green"
                }.get(marker.priority_bucket, "white")
                
                console.print(
                    f"  [{priority_color}]●[/{priority_color}] "
                    f"[dim]{marker.file}:{marker.line}[/dim] — {marker.text[:40]}"
                )
        
        if theme.count > 5:
            console.print(f"  [dim]... and {theme.count - 5} more[/dim]")
        console.print()
    
    if result.ungrouped:
        console.print(f"[dim]Ungrouped: {len(result.ungrouped)} markers[/dim]")


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    console = Console()
    
    console.print("[bold]Testing theme grouping...[/bold]\n")
    
    if not is_configured():
        console.print("[red]❌ ANTHROPIC_API_KEY not set![/red]")
    else:
        # Create test markers
        test_markers = [
            Marker(file="src/auth/login.dart", line=42, marker_type="TODO",
                   text="validate email format", full_line="// TODO: validate email format",
                   author="alice", date="2024-01-15", age_days=300, file_modifications=20,
                   priority_score=0.7, priority_bucket="high"),
            Marker(file="src/auth/register.dart", line=88, marker_type="FIXME",
                   text="password strength check", full_line="// FIXME: password strength check",
                   author="bob", date="2024-02-20", age_days=264, file_modifications=15,
                   priority_score=0.6, priority_bucket="medium"),
            Marker(file="src/api/user_api.dart", line=156, marker_type="TODO",
                   text="handle null response", full_line="// TODO: handle null response",
                   author="alice", date="2024-03-10", age_days=245, file_modifications=30,
                   priority_score=0.8, priority_bucket="high"),
            Marker(file="src/api/product_api.dart", line=203, marker_type="FIXME",
                   text="add null check", full_line="// FIXME: add null check",
                   author="charlie", date="2024-01-05", age_days=310, file_modifications=25,
                   priority_score=0.75, priority_bucket="high"),
            Marker(file="src/utils/cache.dart", line=67, marker_type="TODO",
                   text="implement cache invalidation", full_line="// TODO: implement cache invalidation",
                   author="bob", date="2024-04-01", age_days=223, file_modifications=10,
                   priority_score=0.5, priority_bucket="medium"),
        ]
        
        console.print("Analyzing themes with Gemini...")
        result = group_by_theme(test_markers)
        
        if result:
            print_theme_report(result, test_markers)
        else:
            console.print("[yellow]No themes generated[/yellow]")
