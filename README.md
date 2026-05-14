# tech-debt-finder

CLI tool to find and prioritize stale TODOs, FIXMEs, and code rot in your codebase.

## Installation

```bash
cd tech-debt-finder
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## Usage

### Basic Scanning (CLI Tool)

```bash
# Basic scan
tech-debt-finder scan

# Scan specific path
tech-debt-finder scan ./src

# Only show markers older than 180 days
tech-debt-finder scan --age 180

# Output as JSON (for snapshots)
tech-debt-finder scan --json > snapshots/2026-05-15.json

# Include AI analysis (themes + explanations)
tech-debt-finder scan --analyze

# Scan for dead code (commented-out blocks + dormant files)
tech-debt-finder scan --dead-code

# Generate shareable markdown report (auto-dated filename)
tech-debt-finder scan --report

# Compare two snapshots
tech-debt-finder trend snapshot-old.json snapshot-new.json
```

### 🤖 Agent Mode (AI Agent)

The `agent` command transforms the tool into a true AI agent with a decision loop:

```
SCAN → DECIDE → ACT → NOTIFY
```

```bash
# Preview what would be created (safe mode)
tech-debt-finder agent --repo owner/repo --dry-run

# Create GitHub issues for high-priority tech debt
tech-debt-finder agent --repo shuchitajain/myrepo

# Include medium priority items
tech-debt-finder agent --repo owner/repo --min-priority medium

# Create issues AND send email summary
tech-debt-finder agent --repo owner/repo --notify email --email-to team@company.com

# Group issues by theme (LLM-powered)
tech-debt-finder agent --repo owner/repo --group
```

**Required environment variables:**
```bash
GITHUB_TOKEN=ghp_...           # GitHub personal access token
EMAIL_USER=you@gmail.com       # For email notifications
EMAIL_PASSWORD=xxxx xxxx xxxx  # Gmail app password
```

## LLM Setup (optional, for --analyze)

Set one of these environment variables:

```bash
# Groq (FREE, recommended)
export GROQ_API_KEY=gsk_...  # https://console.groq.com

# Gemini (fallback)
export GOOGLE_API_KEY=...    # https://aistudio.google.com/apikey
```

## Features

- **TODO/FIXME/HACK/TEMP/XXX detection** — with git blame for age and author
- **Commented-out code detection** — heuristics for >3 lines of commented code (`--dead-code`)
- **Dormant files detection** — files nobody has touched in 6+ months (`--dead-code`)
- **Smart prioritization** — age + file activity = priority score
- **AI-powered analysis** — group similar TODOs, explain why to fix first (`--analyze`)
- **Trend tracking** — compare snapshots over time (`trend` command)
- **Markdown reports** — shareable, auto-dated reports (`--report`)

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```
