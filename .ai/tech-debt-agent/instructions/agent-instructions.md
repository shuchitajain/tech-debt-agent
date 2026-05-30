# Tech Debt Agent - Workspace Instructions

This workspace has the **tech-debt-agent** available. It scans the codebase for
tech debt markers (TODO, FIXME, HACK, TEMP, XXX), prioritises them by age and
file activity, and can file GitHub issues for approved items.

## How to use

In agent mode, type:
```
/tech-debt-agent
```

Or natural language: *"scan this repo for tech debt"*, *"find the worst TODOs"*,
*"triage tech debt and create issues"*.

## Agent behaviour

The agent will:
1. Run a full scan and write a prioritised `triage-plan.md`
2. **Ask you for confirmation** before creating any GitHub issues
3. Create issues only for items you approve, with duplicate detection

It will **never** modify source files.

## Prerequisites

- `GITHUB_TOKEN` env var must be set to create issues (repo or public_repo scope)
- The MCP server must be running (configured in `.vscode/mcp.json`)

## MCP server

The agent uses `tech-debt-mcp` as its backend. Tools available:
- `generate_triage_report` - full scan, returns prioritised JSON
- `check_existing_issue` - dedup check before filing
- `create_github_issue` - file an issue
- `mark_wontfix` - exclude a marker from future scans
- `scan_repo`, `get_top_priorities`, `save_tech_debt_snapshot`, `compare_tech_debt_snapshots`, `explain_marker` - read-only scan tools

## Output files

All outputs are written to `.ai/tech-debt-agent/outputs/scans/<YYYY-MM-DD>/`:
- `triage-plan.md` - prioritised list of markers
- `created-issues.md` - summary of issues filed

These are gitignored by default.
