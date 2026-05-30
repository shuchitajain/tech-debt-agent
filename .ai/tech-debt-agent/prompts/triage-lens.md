# Triage Lens - How to Interpret Priority Scores

## Scoring formula (implemented in the MCP server)

```
score = log(age_days + 1) / log(731) × 0.6
      + min(file_modifications / 50, 1) × 0.4
```

Both components are capped at 1.0 and produce a final score between 0.0 and 1.0.

| Bucket | Score range | Meaning |
|--------|-------------|---------|
| High   | > 0.60      | Old debt in an active file. Engineers keep working around it. |
| Medium | > 0.30      | Either old but in a quiet file, or recent but in a hot file. |
| Low    | ≤ 0.30      | Recent and/or in a rarely touched file. Low urgency. |

## What the components mean

**Age component (60% weight)**
- The logarithmic scale compresses raw age: a 2-year-old TODO is not 24× more urgent than a 1-month-old one.
- `age_days = 0` → age_score = 0.0
- `age_days ≈ 90` → age_score ≈ 0.5
- `age_days ≥ 730` → age_score = 1.0 (capped)

**Activity component (40% weight)**
- `file_modifications` = number of git commits touching that file since the marker was added.
- A file with 50+ commits is considered "maximally active" (score = 1.0).
- This component answers: *"Is this code still being worked on?"* A TODO buried in a file nobody opens is lower priority than the same TODO in a file touched every sprint.

## Decision guidelines for the agent

When writing the triage plan, use these signals to annotate each item with context:

| Signal | Interpretation |
|--------|---------------|
| `age_days > 365` AND `file_modifications > 20` | This is the highest-signal debt. Old problem, active file. File an issue. |
| `age_days > 180` AND type = `FIXME` | FIXME implies broken behaviour, not just cleanup. Escalate regardless of activity. |
| `age_days < 60` | Probably introduced in a recent feature branch. May self-resolve. Flag but don't auto-file. |
| `type = HACK` | Usually implies a known-bad workaround. Higher filing priority than `TODO` at the same score. |
| `type = TODO` AND `age_days < 90` | Low urgency. Include in plan but recommend medium/low label. |
| `file_modifications = 0` | Dead file or dormant path. Low priority regardless of age. |

## Marker type priority order (when scores are equal)

`FIXME` > `HACK` > `XXX` > `TEMP` > `TODO`

## When NOT to file an issue

- Marker fingerprint exists in `.tech-debt-wontfix.json` in the repo root → skip entirely.
- Score < 0.3 unless the user explicitly asked to include low-priority items.
- `file_modifications = 0` AND `age_days < 365` → not worth filing.
- Duplicate already exists on GitHub (check via `check_existing_issue`).
