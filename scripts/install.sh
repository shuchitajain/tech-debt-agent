#!/usr/bin/env bash
# install.sh - Zero-clone installer for tech-debt-agent
#
# Usage (from your project root):
#   curl -fsSL https://raw.githubusercontent.com/shuchitajain/tech-debt-agent/main/scripts/install.sh | bash
#
# Or with an explicit target path:
#   curl -fsSL https://raw.githubusercontent.com/shuchitajain/tech-debt-agent/main/scripts/install.sh | bash -s -- /path/to/project
#
# What this does:
#   1. Downloads agent files from GitHub directly (no clone required)
#   2. Merges MCP server config into .vscode/mcp.json, .cursor/mcp.json, .mcp.json
#   3. Installs Copilot agent + prompt wrappers into .github/agents/ and .github/prompts/
#   4. Appends agent reference to CLAUDE.md / .cursorrules / copilot-instructions.md
#   5. Adds output directory to .gitignore
#
# Safe to run multiple times - all operations are idempotent.

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────

REPO="shuchitajain/tech-debt-agent"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/$REPO/$BRANCH"
TARGET="${1:-$(pwd)}"

# ── Helpers ───────────────────────────────────────────────────────────────────

download() {
  local url="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  if command -v curl &>/dev/null; then
    curl -fsSL "$url" -o "$dest"
  elif command -v wget &>/dev/null; then
    wget -qO "$dest" "$url"
  else
    echo "Error: curl or wget required" >&2
    exit 1
  fi
}

# ── Validate target ───────────────────────────────────────────────────────────

if [[ ! -d "$TARGET" ]]; then
  echo "Error: target directory does not exist: $TARGET" >&2
  exit 1
fi

TARGET="$(cd "$TARGET" && pwd)"
echo "Installing tech-debt-agent into: $TARGET"

# ── 1. Download agent files ───────────────────────────────────────────────────

AGENT_FILES=(
  ".ai/tech-debt-agent/agents/tech-debt-agent.md"
  ".ai/tech-debt-agent/instructions/agent-instructions.md"
  ".ai/tech-debt-agent/prompts/triage-lens.md"
  ".ai/tech-debt-agent/prompts/issue-format.md"
)

for file in "${AGENT_FILES[@]}"; do
  dest="$TARGET/$file"
  if [[ -f "$dest" ]]; then
    echo "Already exists, skipping: $file"
  else
    download "$RAW_BASE/$file" "$dest"
    echo "Downloaded: $file"
  fi
done

mkdir -p "$TARGET/.ai/tech-debt-agent/outputs/scans"

# ── 2. Merge MCP config ───────────────────────────────────────────────────────

MCP_SERVER_BLOCK='{
  "type": "stdio",
  "command": "uvx",
  "args": ["--from", "git+https://github.com/shuchitajain/tech-debt-agent", "tech-debt-mcp"],
  "envFile": "${workspaceFolder}/.env"
}'

merge_mcp_json() {
  local config_file="$1"
  local server_key="$2"

  if [[ ! -f "$config_file" ]]; then
    mkdir -p "$(dirname "$config_file")"
    echo "{ \"$server_key\": { \"tech-debt-mcp\": $MCP_SERVER_BLOCK } }" \
      | python3 -m json.tool > "$config_file"
    echo "Created $config_file"
    return
  fi

  if python3 -c "
import json, sys
data = json.load(open('$config_file'))
sys.exit(0 if 'tech-debt-mcp' in data.get('$server_key', {}) else 1)
" 2>/dev/null; then
    echo "Already configured in $config_file - skipping"
    return
  fi

  python3 -c "
import json
with open('$config_file') as f:
    data = json.load(f)
if '$server_key' not in data:
    data['$server_key'] = {}
data['$server_key']['tech-debt-mcp'] = json.loads('''$MCP_SERVER_BLOCK''')
with open('$config_file', 'w') as f:
    json.dump(data, f, indent=2)
print('Merged tech-debt-mcp into $config_file')
"
}

merge_mcp_json "$TARGET/.vscode/mcp.json"  "servers"
merge_mcp_json "$TARGET/.cursor/mcp.json"  "mcpServers"
merge_mcp_json "$TARGET/.mcp.json"         "mcpServers"

# ── 3. Copilot team-shared agent ─────────────────────────────────────────────
# .github/agents/ is where Copilot discovers team-shared agents (mode dropdown)

AGENT_SRC_URL="$RAW_BASE/.ai/tech-debt-agent/agents/tech-debt-agent.md"
AGENTS_DEST="$TARGET/.github/agents/tech-debt-agent.md"
if [[ ! -f "$AGENTS_DEST" ]]; then
  download "$AGENT_SRC_URL" "$AGENTS_DEST"
  echo "Installed Copilot agent: $AGENTS_DEST"
else
  echo "Already exists, skipping: .github/agents/tech-debt-agent.md"
fi

# ── 4. Inject agent reference into AI instruction files ──────────────────────

AGENT_REFERENCE_BLOCK="
## tech-debt-agent
This workspace has the tech-debt-agent installed. Use \`/tech-debt-agent\` in agent
mode to scan for tech debt and file GitHub issues. Full instructions:
\`.ai/tech-debt-agent/instructions/agent-instructions.md\`
"

inject_if_missing() {
  local file="$1"
  if [[ -f "$file" ]] && ! grep -q "tech-debt-agent" "$file"; then
    printf '%s' "$AGENT_REFERENCE_BLOCK" >> "$file"
    echo "Appended agent reference to $file"
  fi
}

inject_if_missing "$TARGET/CLAUDE.md"
inject_if_missing "$TARGET/.cursorrules"
inject_if_missing "$TARGET/.github/copilot-instructions.md"

# ── 5. Update .gitignore ──────────────────────────────────────────────────────

GITIGNORE="$TARGET/.gitignore"
GITIGNORE_ENTRY=".ai/tech-debt-agent/outputs/"

if [[ -f "$GITIGNORE" ]]; then
  if ! grep -qF "$GITIGNORE_ENTRY" "$GITIGNORE"; then
    printf '\n# tech-debt-agent scan outputs\n%s\n' "$GITIGNORE_ENTRY" >> "$GITIGNORE"
    echo "Added $GITIGNORE_ENTRY to .gitignore"
  fi
else
  printf '# tech-debt-agent scan outputs\n%s\n' "$GITIGNORE_ENTRY" > "$GITIGNORE"
  echo "Created .gitignore with $GITIGNORE_ENTRY"
fi

# ── 6. GitHub label (optional) ───────────────────────────────────────────────

if command -v gh &>/dev/null; then
  REMOTE_URL="$(git -C "$TARGET" remote get-url origin 2>/dev/null || true)"
  if [[ -n "$REMOTE_URL" ]]; then
    REPO_SLUG="$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')"
    if gh label list --repo "$REPO_SLUG" 2>/dev/null | grep -q "tech-debt"; then
      echo "Label 'tech-debt' already exists in $REPO_SLUG"
    else
      gh label create tech-debt --repo "$REPO_SLUG" --color "E4E669" \
        --description "Tech debt marker filed by tech-debt-agent" 2>/dev/null \
        && echo "Created 'tech-debt' label in $REPO_SLUG" \
        || echo "Could not create label - create it manually in GitHub"
    fi
  fi
else
  echo "gh CLI not found - create a 'tech-debt' label manually in your GitHub repo"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "tech-debt-agent installed successfully."
echo ""
echo "Next steps:"
echo "  1. Set GITHUB_TOKEN in your .env file (repo or public_repo scope)"
echo "  2. Reload your IDE to pick up the new MCP server"
echo "  3. Open agent mode and type: /tech-debt-agent"
echo ""
echo "Docs: $TARGET/.ai/tech-debt-agent/instructions/agent-instructions.md"
