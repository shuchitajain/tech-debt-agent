# tech-debt-finder

CLI tool to find and prioritize stale TODOs, FIXMEs, and code rot in your codebase.
SCAN → DECIDE → ACT → NOTIFY

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

### 🔌 MCP Server (Copilot / Claude / Cursor integration)

Expose the same scan/prioritize/trend functions as tools any MCP-aware AI agent
can call. Once configured, you can ask GitHub Copilot in agent mode:

> *"What's the worst tech debt in this repo?"*
> *"Compare snapshots/2026-05-01.json against snapshots/2026-05-15.json"*
> *"Tell me about the TODO at lib/main.dart line 142"*

Copilot picks the right tool, calls it, and reasons about the structured response.

#### Installation (for your teammates)

This repo is private, so install over SSH (or HTTPS + a personal access token).
`pipx` installs the package into an isolated venv and puts the `tech-debt-mcp`
command on your system PATH — no manual venv activation needed.

**1. Install `pipx` (one-time, if you don't have it):**

```bash
# macOS
brew install pipx
pipx ensurepath

# Linux / Windows
python -m pip install --user pipx
python -m pipx ensurepath
```

Restart your terminal after `ensurepath`.

**2. Confirm GitHub access:**

```bash
ssh -T git@github.com   # should say "Hi <username>!"
```

If that fails, add an SSH key to your GitHub account, or use the HTTPS+token
variant in step 3.

**3. Install tech-debt-finder:**

```bash
# Recommended: SSH (uses your existing GitHub SSH key, nothing to share)
pipx install git+ssh://git@github.com/shuchitajain/tech-debt-finder.git

# Alternative: HTTPS + personal access token
pipx install "git+https://<YOUR_PAT>@github.com/shuchitajain/tech-debt-finder.git"
```

**4. Verify:**

```bash
which tech-debt-mcp        # should print a path under ~/.local/...
tech-debt-finder --help    # CLI also works
```

**5. Configure your editor** — add `.vscode/mcp.json` to any repo you want to
scan (commit this file so the whole team gets it automatically):

```json
{
  "servers": {
    "tech-debt-finder": {
      "type": "stdio",
      "command": "tech-debt-mcp"
    }
  }
}
```

**6. Use it** — open Copilot Chat → switch the mode dropdown to **Agent** →
the `tech-debt-finder` tools show in the tool picker. Try:

> *"Use tech-debt-finder to list the top 5 issues in this repo as a bulleted list."*

#### Updating

```bash
pipx upgrade tech-debt-finder
```

#### Uninstalling

```bash
pipx uninstall tech-debt-finder
```

#### Available MCP tools

| Tool | Purpose |
|---|---|
| `scan_repo` | Full scan with prioritization; returns all markers + summary |
| `get_top_priorities` | Top N highest-priority markers (for "what should I fix first?") |
| `save_tech_debt_snapshot` | Scan and persist results to a JSON file |
| `compare_tech_debt_snapshots` | Diff two snapshots; returns resolved/added markers + trend |
| `explain_marker` | Full details for one marker by file + line number |

The MCP server is launched on demand by your IDE — no daemon to manage.

#### Troubleshooting

- **Tools don't appear in Copilot:** confirm Copilot Chat is in **Agent** mode
  (mode dropdown at the top of the chat). MCP tools don't show in Ask or Edit modes.
- **Server shows "failed to start":** run `tech-debt-mcp` in a terminal — if it
  hangs silently it's working (waiting for stdio JSON-RPC). If it errors, the
  install is broken; re-run `pipx install --force ...`.
- **Path with spaces:** if you reference an absolute path in `mcp.json`, put it
  entirely inside the `"command"` string. JSON handles spaces; don't split into
  `command` + `args`.
- **Restart after code changes:** Cmd+Shift+P → **MCP: List Servers** →
  `tech-debt-finder` → Restart.

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
