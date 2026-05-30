# Contributing

Thanks for your interest in contributing to tech-debt-finder.

## What to work on

Check the open issues. Anything labeled `good first issue` is a good starting point.

If you want to propose something new, open an issue first before writing code. It avoids wasted effort if the direction doesn't fit.

## Setup

```bash
git clone https://github.com/shuchitajain/tech-debt-agent
cd tech-debt-finder
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

## What's in scope

- New MCP tools in `server.py`
- Improvements to the priority scoring formula in `prioritizer.py`
- New agent prompt files under `.ai/tech-debt-agent/`
- Fixes to `install.sh`
- Additional tracker support (Jira, Linear, Azure DevOps) via new files in `src/`

## What's out of scope

- Reintroducing a CLI
- LLM integrations in the Python layer (the host IDE's LLM handles reasoning)
- Breaking changes to existing MCP tool signatures without a migration path

## Pull requests

- Keep PRs focused. One thing per PR.
- Update `examples/` if your change affects agent output format.
- Run `pytest` before opening a PR.

## Questions

Open an issue or reach out on [LinkedIn](https://www.linkedin.com/in/shuchita-jain/).
