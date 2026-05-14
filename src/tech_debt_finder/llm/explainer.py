"""
explainer.py — Generate priority explanations using Gemini

WHY EXPLAIN PRIORITIES?
=======================
A score of 0.87 doesn't tell engineers WHY something matters.
Gemini turns the raw metrics into actionable insights:

Instead of: "TODO at auth.dart:142, score: 0.87"
We get: "Fix this first because: this 14-month old auth TODO is in your 
        most-modified file (34 changes). Stale auth code + high churn = 
        likely source of future bugs."

The LLM considers:
- Age (how long has this been rotting?)
- File activity (hot file = high risk)
- Marker type (FIXME > HACK > TODO)
- File path context (auth, payments = critical areas)
"""

import json
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from tech_debt_finder.scanner import Marker
from tech_debt_finder.json_output import generate_fingerprint
from tech_debt_finder.llm.client import chat_completion, is_configured


@dataclass
class PriorityExplanation:
    """Explanation for a single marker's priority."""
    fingerprint: str
    summary: str  # One-line summary
    reasoning: str  # Detailed reasoning
    suggested_action: str  # What to do about it


@dataclass
class ExplanationResult:
    """Result of priority explanation."""
    explanations: list[PriorityExplanation]
    overall_summary: str  # High-level summary of the debt situation


# System prompt for explanations
SYSTEM_PROMPT = """You are a senior software engineer reviewing technical debt. Your task is to explain why certain TODO/FIXME markers should be prioritized.

Your explanations should be:
1. SPECIFIC — reference actual metrics (age, file modifications, file paths)
2. ACTIONABLE — tell them what to do
3. BUSINESS-AWARE — highlight risks (auth issues, data integrity, UX)
4. CONCISE — one sentence summary, 2-3 sentence reasoning

NEVER be generic. Bad: "This is old and should be fixed." 
Good: "This 14-month-old auth TODO sits in a file with 34 recent changes—high churn + stale security code is a bug waiting to happen."

Output ONLY valid JSON, no markdown code blocks."""


def _build_user_prompt(markers: list[Marker]) -> str:
    """Build the user prompt with marker data."""
    marker_data = []
    for m in markers:
        marker_data.append({
            "fingerprint": generate_fingerprint(m),
            "file": m.file,
            "line": m.line,
            "type": m.marker_type,
            "text": m.text,
            "author": m.author,
            "age_days": m.age_days,
            "file_modifications": m.file_modifications,
            "priority_score": round(m.priority_score, 2),
            "priority_bucket": m.priority_bucket,
        })
    
    return f"""Analyze these {len(markers)} high-priority code markers and explain why they matter.

MARKERS (already sorted by priority):
{json.dumps(marker_data, indent=2)}

Return JSON in this exact format:
{{
    "overall_summary": "One paragraph summarizing the tech debt situation",
    "explanations": [
        {{
            "fingerprint": "abc123",
            "summary": "One-line summary (max 80 chars)",
            "reasoning": "2-3 sentences explaining why this matters",
            "suggested_action": "What to do about it"
        }}
    ]
}}

Focus on the TOP markers. Be specific about WHY each one is risky."""


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


def _parse_response(response_text: str) -> ExplanationResult:
    """Parse LLM's response into structured result."""
    text = _extract_json(response_text)
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        console = Console()
        console.print(f"[yellow]Warning: Could not parse LLM response: {e}[/yellow]")
        return ExplanationResult(explanations=[], overall_summary="Analysis unavailable")
    
    explanations = []
    for e in data.get("explanations", []):
        explanations.append(PriorityExplanation(
            fingerprint=e.get("fingerprint", ""),
            summary=e.get("summary", ""),
            reasoning=e.get("reasoning", ""),
            suggested_action=e.get("suggested_action", ""),
        ))
    
    return ExplanationResult(
        explanations=explanations,
        overall_summary=data.get("overall_summary", ""),
    )


def explain_priorities(markers: list[Marker], top_n: int = 5) -> Optional[ExplanationResult]:
    """
    Generate explanations for high-priority markers.
    
    Args:
        markers: List of Marker objects (should be sorted by priority)
        top_n: How many top markers to explain
        
    Returns:
        ExplanationResult with detailed explanations,
        or None if LLM is not configured
    """
    if not is_configured():
        return None
    
    if not markers:
        return None
    
    # Take only top N markers
    top_markers = markers[:top_n]
    
    user_prompt = _build_user_prompt(top_markers)
    
    response = chat_completion(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=2048,
        temperature=0.3,
    )
    
    return _parse_response(response)


def print_explanations(result: ExplanationResult, markers: list[Marker]) -> None:
    """Print formatted priority explanations."""
    console = Console()
    
    # Create fingerprint -> marker lookup
    fp_to_marker = {generate_fingerprint(m): m for m in markers}
    
    console.print("\n[bold blue]🎯 Priority Analysis[/bold blue]")
    
    # Overall summary
    if result.overall_summary:
        console.print(Panel(
            result.overall_summary,
            title="Overview",
            border_style="blue",
        ))
    
    console.print()
    
    # Individual explanations
    for i, exp in enumerate(result.explanations, 1):
        marker = fp_to_marker.get(exp.fingerprint)
        if not marker:
            continue
        
        priority_color = {
            "high": "red",
            "medium": "yellow",
            "low": "green"
        }.get(marker.priority_bucket, "white")
        
        # Header with file info
        console.print(
            f"[bold]{i}. [{priority_color}]{marker.marker_type}[/{priority_color}][/bold] "
            f"[dim]{marker.file}:{marker.line}[/dim]"
        )
        console.print(f"   [cyan]{marker.text}[/cyan]")
        
        # Metrics (human-readable, no raw score)
        age_str = f"{marker.age_days} days old" if marker.age_days > 0 else "just added"
        churn_str = f"{marker.file_modifications} file changes"
        priority_label = marker.priority_bucket.upper()
        
        console.print(
            f"   [dim]{age_str} | {churn_str} | "
            f"[{priority_color}]{priority_label} priority[/{priority_color}][/dim]"
        )
        
        # AI explanation
        console.print(f"\n   [bold]Why it matters:[/bold] {exp.summary}")
        console.print(f"   {exp.reasoning}")
        console.print(f"\n   [green]→ {exp.suggested_action}[/green]")
        console.print()


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    console = Console()
    
    console.print("[bold]Testing priority explanations...[/bold]\n")
    
    if not is_configured():
        console.print("[red]❌ ANTHROPIC_API_KEY not set![/red]")
    else:
        # Create test markers
        test_markers = [
            Marker(file="src/auth/token_manager.dart", line=142, marker_type="TODO",
                   text="handle token refresh on 401", full_line="// TODO: handle token refresh on 401",
                   author="alice", date="2024-01-15", age_days=420, file_modifications=34,
                   priority_score=0.92, priority_bucket="high"),
            Marker(file="src/payments/checkout.dart", line=88, marker_type="FIXME",
                   text="validate card number before submit", full_line="// FIXME: validate card number before submit",
                   author="bob", date="2024-02-20", age_days=384, file_modifications=28,
                   priority_score=0.85, priority_bucket="high"),
            Marker(file="src/api/user_api.dart", line=203, marker_type="HACK",
                   text="hardcoded timeout, should be config", full_line="// HACK: hardcoded timeout, should be config",
                   author="charlie", date="2024-03-10", age_days=365, file_modifications=45,
                   priority_score=0.78, priority_bucket="high"),
        ]
        
        console.print("Generating explanations with Gemini...")
        result = explain_priorities(test_markers, top_n=3)
        
        if result:
            print_explanations(result, test_markers)
        else:
            console.print("[yellow]No explanations generated[/yellow]")
