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

from pathlib import Path

import typer
from rich.console import Console

from tech_debt_finder.scanner import scan_directory, filter_by_age
from tech_debt_finder.git_utils import enrich_markers
from tech_debt_finder.prioritizer import prioritize_markers
from tech_debt_finder.reporter import (
    print_report,
    print_scanning_message,
    print_enriching_message,
    print_done_message,
    print_no_markers_found,
)


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
    dead_code: bool = typer.Option(
        False,
        "--dead-code", "-d",
        help="Also scan for commented-out code blocks and dormant files."
    ),
    all_markers: bool = typer.Option(
        False,
        "--all",
        help="Show all markers (by default, limits to 10 per priority level)."
    ),
    report: bool = typer.Option(
        False,
        "--report", "-r",
        help="Generate a markdown report file (auto-named with date)."
    ),
):
    """
    Scan for TODOs, FIXMEs, and code rot.
    
    Examples:
        tech-debt-finder scan
        tech-debt-finder scan ./src --age 180
        tech-debt-finder scan --json > snapshot.json
        tech-debt-finder scan --analyze
        tech-debt-finder scan --dead-code
    """
    # Convert string path to Path object
    scan_path = Path(path).resolve()
    
    # For display, use folder name if scanning "." (current dir)
    display_path = scan_path.name if path == "." else str(scan_path)
    
    # Validate path exists
    if not scan_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(code=1)
    
    # Step 1: Scan for markers (quiet mode for JSON output)
    if not json_output:
        print_scanning_message(display_path)
    markers = scan_directory(scan_path)
    
    if not markers:
        if not json_output:
            print_no_markers_found(display_path)
        return
    
    # Step 2: Enrich with git info
    if not json_output:
        print_enriching_message(len(markers))
    enrich_markers(markers)
    
    # Step 3: Calculate priorities
    markers = prioritize_markers(markers)
    
    # Step 4: Filter by age if requested
    if age > 0:
        markers = filter_by_age(markers, age)
        if not markers:
            if not json_output:
                console.print(f"[yellow]No markers older than {age} days.[/yellow]")
            return
    
    if not json_output:
        print_done_message()
    
    # Step 5: Output results
    if json_output:
        # JSON output for snapshots
        # Use regular print(), NOT console.print() — Rich wraps long lines!
        from tech_debt_finder.json_output import snapshot_to_json
        json_str = snapshot_to_json(markers, str(scan_path))
        print(json_str)
    elif analyze:
        # AI analysis
        from tech_debt_finder.llm import is_configured, group_by_theme, explain_priorities
        from tech_debt_finder.llm.client import _get_provider
        from tech_debt_finder.llm.theme_grouper import print_theme_report
        from tech_debt_finder.llm.explainer import print_explanations
        
        if not is_configured():
            console.print("[red]Error:[/red] No LLM API key configured.")
            console.print("Set one of:")
            console.print("  GROQ_API_KEY=... (https://console.groq.com)")
            console.print("  GOOGLE_API_KEY=... (https://aistudio.google.com/apikey)")
            raise typer.Exit(code=1)
        
        # First, show normal report
        print_report(markers, display_path, show_all=all_markers)
        
        # Then, add AI insights
        provider = _get_provider().upper()
        console.print(f"\n[bold blue]🤖 AI Analysis[/bold blue] (powered by {provider})")
        
        # Theme grouping
        console.print("\nGrouping TODOs by theme...")
        theme_result = group_by_theme(markers)
        if theme_result:
            print_theme_report(theme_result, markers)
        
        # Priority explanations for top 5
        console.print("\nAnalyzing top priorities...")
        explain_result = explain_priorities(markers, top_n=5)
        if explain_result:
            print_explanations(explain_result, markers)
    else:
        # Normal terminal report
        print_report(markers, display_path, show_all=all_markers)
    
    # Dead code detection (optional)
    commented_blocks = []
    dormant_files = []
    if dead_code:
        from tech_debt_finder.scanner import scan_for_commented_code, CommentedCodeBlock
        from tech_debt_finder.git_utils import find_dormant_files, DormantFile
        from tech_debt_finder.reporter import print_dead_code_report
        
        console.print("\n[bold]🔍 Scanning for dead code...[/bold]")
        
        # Find commented-out code blocks
        commented_blocks = scan_for_commented_code(scan_path)
        
        # Find dormant files (not modified in 6 months)
        dormant_files = find_dormant_files(scan_path, dormant_days=180)
        
        print_dead_code_report(commented_blocks, dormant_files)
    
    # Generate markdown report (optional)
    if report:
        from datetime import date
        from tech_debt_finder.reporter import generate_markdown_report
        
        # Auto-generate filename with today's date
        report_path = Path(f"tech-debt-{date.today().isoformat()}.md")
        md_content = generate_markdown_report(
            markers=markers,
            scan_path=display_path,
            commented_blocks=commented_blocks if dead_code else None,
            dormant_files=dormant_files if dead_code else None,
        )
        report_path.write_text(md_content)
        console.print(f"\n[green]📄 Report saved:[/green] {report_path}")


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
    from tech_debt_finder.trend import compare_snapshot_files, print_trend_report
    
    # Validate files exist
    if not Path(file1).exists():
        console.print(f"[red]Error:[/red] File not found: {file1}")
        raise typer.Exit(code=1)
    if not Path(file2).exists():
        console.print(f"[red]Error:[/red] File not found: {file2}")
        raise typer.Exit(code=1)
    
    # Compare and report
    report = compare_snapshot_files(file1, file2)
    print_trend_report(report)


@app.command()
def version():
    """Show version information."""
    from tech_debt_finder import __version__
    console.print(f"tech-debt-finder version [bold green]{__version__}[/]")


@app.command()
def agent(
    path: str = typer.Argument(
        ".",
        help="Path to scan (file or directory)."
    ),
    tracker: str = typer.Option(
        "github",
        "--tracker", "-t",
        help="Issue tracker to use: github, jira, azure"
    ),
    repo: str = typer.Option(
        None,
        "--repo", "-r",
        help="GitHub repo in format 'owner/repo' (e.g., 'shuchitajain/tech-debt-finder')"
    ),
    notify: str = typer.Option(
        None,
        "--notify", "-n",
        help="Notification channel: email, slack, teams"
    ),
    email_to: str = typer.Option(
        None,
        "--email-to",
        help="Email recipient (required if --notify=email)"
    ),
    min_priority: str = typer.Option(
        "high",
        "--min-priority",
        help="Minimum priority to create issues for: high, medium, low"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be created without actually creating issues"
    ),
    group_by_theme: bool = typer.Option(
        True,
        "--group/--no-group",
        help="Group markers by theme (1 issue per theme) vs individual issues"
    ),
):
    """
    🤖 AI AGENT MODE: Scan, decide, and take action.
    
    This command transforms the tool from a passive scanner into an active agent:
    
    1. SCAN — Find all tech debt markers
    2. DECIDE — Filter by priority, group by theme
    3. ACT — Create issues in your tracker
    4. NOTIFY — Send summary to your team
    
    Examples:
        # Preview what would be created
        tech-debt-finder agent --repo owner/repo --dry-run
        
        # Create GitHub issues for high-priority items
        tech-debt-finder agent --repo shuchitajain/myrepo
        
        # Create issues and send email summary
        tech-debt-finder agent --repo owner/repo --notify email --email-to team@company.com
        
        # Include medium priority items
        tech-debt-finder agent --repo owner/repo --min-priority medium
    
    Required environment variables:
        GITHUB_TOKEN — for GitHub tracker
        EMAIL_USER, EMAIL_PASSWORD — for email notifications (Gmail app password)
    """
    from tech_debt_finder.prioritizer import group_by_priority
    
    # Validate required options
    if tracker == "github" and not repo:
        console.print("[red]Error:[/red] --repo required for GitHub tracker (e.g., --repo owner/repo)")
        raise typer.Exit(code=1)
    
    if notify == "email" and not email_to:
        console.print("[red]Error:[/red] --email-to required when using email notifications")
        raise typer.Exit(code=1)
    
    scan_path = Path(path).resolve()
    display_path = scan_path.name if path == "." else str(scan_path)
    
    if not scan_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(code=1)
    
    # =========================================================================
    # STEP 1: SCAN — Same as regular scan command
    # =========================================================================
    console.print(f"\n[bold blue]🤖 Agent Mode[/bold blue]")
    console.print(f"[dim]Scanning: {display_path}[/dim]\n")
    
    console.print("[bold]Step 1:[/bold] 🔍 Scanning for tech debt...")
    markers = scan_directory(scan_path)
    
    if not markers:
        console.print("[green]✨ No tech debt found! Nothing to do.[/green]")
        return
    
    # Enrich with git info
    enrich_markers(markers)
    markers = prioritize_markers(markers)
    
    console.print(f"  Found {len(markers)} markers")
    
    # =========================================================================
    # STEP 2: DECIDE — Filter by priority
    # =========================================================================
    console.print(f"\n[bold]Step 2:[/bold] 🧠 Deciding what to act on...")
    
    groups = group_by_priority(markers)
    priority_order = ["high", "medium", "low"]
    
    # Filter markers based on minimum priority
    actionable_markers = []
    for p in priority_order:
        actionable_markers.extend(groups[p])
        if p == min_priority:
            break
    
    console.print(f"  Priority filter: {min_priority}+")
    console.print(f"  Actionable markers: {len(actionable_markers)}")
    
    if not actionable_markers:
        console.print(f"[yellow]No markers meet the {min_priority}+ priority threshold.[/yellow]")
        return
    
    # Group by theme if requested (using LLM)
    themes = None
    if group_by_theme and len(actionable_markers) > 1:
        from tech_debt_finder.llm import is_configured, group_by_theme as llm_group
        
        if is_configured():
            console.print("  Grouping by theme (LLM)...")
            themes = llm_group(actionable_markers)
    
    # =========================================================================
    # STEP 3: ACT — Create issues
    # =========================================================================
    console.print(f"\n[bold]Step 3:[/bold] 🎯 Taking action...")
    
    if dry_run:
        console.print("[yellow]  DRY RUN — No issues will be created[/yellow]")
    
    # Initialize tracker (skip in dry-run mode)
    issue_tracker = None
    if not dry_run:
        try:
            from tech_debt_finder.trackers import get_tracker
            
            if tracker == "github":
                owner, repo_name = repo.split("/")
                issue_tracker = get_tracker("github", owner=owner, repo=repo_name)
            else:
                console.print(f"[red]Tracker '{tracker}' not yet implemented[/red]")
                raise typer.Exit(code=1)
            
            console.print(f"  Using tracker: {issue_tracker.get_name()}")
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)
    else:
        console.print(f"  Would use tracker: {tracker}")
    
    # Create issues
    issues_created = []
    issues_skipped = []
    
    # Build fingerprint -> marker index mapping for theme grouping
    from tech_debt_finder.json_output import generate_fingerprint
    fingerprint_to_idx = {generate_fingerprint(m): i for i, m in enumerate(actionable_markers)}
    
    if themes and hasattr(themes, 'themes') and themes.themes:
        # Create one issue per theme
        console.print(f"  Creating issues by theme ({len(themes.themes)} themes)...")
        
        for theme in themes.themes:
            title = f"Tech Debt: {theme.name}"
            
            # Find markers by fingerprint
            theme_markers = []
            for fp in theme.fingerprints:
                if fp in fingerprint_to_idx:
                    theme_markers.append(actionable_markers[fingerprint_to_idx[fp]])
            
            # Build issue body
            body_lines = [
                f"## {theme.name}",
                "",
                f"**{len(theme_markers)} related items found by tech-debt-finder**",
                "",
                f"_{theme.description}_",
                "",
                "### Items",
            ]
            
            for m in theme_markers:
                body_lines.append(f"- `{m.file}:{m.line}` — {m.marker_type}: {m.text}")
            
            body_lines.extend([
                "",
                "---",
                "*Auto-generated by tech-debt-finder agent*",
            ])
            
            body = "\n".join(body_lines)
            labels = ["tech-debt", "auto-generated"]
            
            if dry_run:
                console.print(f"  [dim]Would create:[/dim] {title}")
                issues_created.append({"title": title, "url": "(dry-run)", "tracker": tracker})
            else:
                result = issue_tracker.create_issue(title, body, labels)
                if result.success:
                    console.print(f"  [green]✓[/green] Created: {title}")
                    console.print(f"    [dim]{result.issue_url}[/dim]")
                    issues_created.append({
                        "title": title,
                        "url": result.issue_url,
                        "tracker": tracker,
                    })
                elif result.skipped_reason:
                    console.print(f"  [yellow]⊘[/yellow] Skipped: {title}")
                    console.print(f"    [dim]{result.skipped_reason}[/dim]")
                    issues_skipped.append(title)
                else:
                    console.print(f"  [red]✗[/red] Failed: {title}")
                    console.print(f"    [dim]{result.error}[/dim]")
    else:
        # Create one issue for all items
        title = f"Tech Debt: {len(actionable_markers)} items in {display_path}"
        
        body_lines = [
            f"## Tech Debt Report",
            "",
            f"**{len(actionable_markers)} items found by tech-debt-finder**",
            "",
            "### Items",
        ]
        
        for m in actionable_markers[:20]:  # Limit to 20 items
            body_lines.append(f"- `{m.file}:{m.line}` — {m.marker_type}: {m.text}")
        
        if len(actionable_markers) > 20:
            body_lines.append(f"- ... and {len(actionable_markers) - 20} more")
        
        body_lines.extend([
            "",
            "---",
            "*Auto-generated by tech-debt-finder agent*",
        ])
        
        body = "\n".join(body_lines)
        labels = ["tech-debt", "auto-generated"]
        
        if dry_run:
            console.print(f"  [dim]Would create:[/dim] {title}")
            issues_created.append({"title": title, "url": "(dry-run)", "tracker": tracker})
        else:
            result = issue_tracker.create_issue(title, body, labels)
            if result.success:
                console.print(f"  [green]✓[/green] Created: {title}")
                console.print(f"    [dim]{result.issue_url}[/dim]")
                issues_created.append({
                    "title": title,
                    "url": result.issue_url,
                    "tracker": tracker,
                })
            elif result.skipped_reason:
                console.print(f"  [yellow]⊘[/yellow] Skipped: {title}")
                console.print(f"    [dim]{result.skipped_reason}[/dim]")
            else:
                console.print(f"  [red]✗[/red] Failed: {title}")
                console.print(f"    [dim]{result.error}[/dim]")
    
    # =========================================================================
    # STEP 4: NOTIFY — Send summary
    # =========================================================================
    if notify:
        console.print(f"\n[bold]Step 4:[/bold] 📣 Sending notification...")
        
        try:
            from tech_debt_finder.notifiers import get_notifier
            
            if notify == "email":
                notifier = get_notifier("email", to_address=email_to)
            else:
                console.print(f"[red]Notifier '{notify}' not yet implemented[/red]")
                raise typer.Exit(code=1)
            
            subject = f"Tech Debt Agent Report: {display_path}"
            body = f"Scanned {display_path} and found {len(actionable_markers)} actionable items."
            
            if dry_run:
                console.print(f"  [dim]Would notify via {notifier.get_name()}[/dim]")
            else:
                result = notifier.send_summary(subject, body, issues_created)
                if result.success:
                    console.print(f"  [green]✓[/green] Notification sent via {notifier.get_name()}")
                else:
                    console.print(f"  [red]✗[/red] Notification failed: {result.error}")
        
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    console.print(f"\n[bold green]✅ Agent run complete![/bold green]")
    console.print(f"  Issues created: {len(issues_created)}")
    console.print(f"  Issues skipped: {len(issues_skipped)}")
    if dry_run:
        console.print(f"  [yellow](Dry run — nothing was actually created)[/yellow]")


# This allows running the file directly: python -m tech_debt_finder.cli
if __name__ == "__main__":
    app()
