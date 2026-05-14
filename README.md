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

```bash
# Basic scan
tech-debt-finder scan

# Scan specific path
tech-debt-finder scan ./src

# Only show markers older than 180 days
tech-debt-finder scan --age 180

# Output as JSON (for snapshots)
tech-debt-finder scan --json > snapshots/2025-05-14.json

# Include AI analysis (themes + explanations)
tech-debt-finder scan --analyze

# Compare two snapshots
tech-debt-finder trend snapshot-old.json snapshot-new.json
```

## Features

- **TODO/FIXME/HACK/TEMP/XXX detection** — with git blame for age and author
- **Commented-out code detection** — heuristics for >3 lines of commented code
- **Dormant files detection** — files nobody has touched in months
- **Smart prioritization** — age + file activity = priority score
- **AI-powered analysis** — group similar TODOs, explain why to fix first
- **Trend tracking** — compare snapshots over time

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```
