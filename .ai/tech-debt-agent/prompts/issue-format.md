# Issue Format - GitHub Issue Title and Body Templates

## Title format

```
[tech-debt] <TYPE>: <short description> (<file>)
```

Rules:
- `<TYPE>` is the marker type in uppercase: `TODO`, `FIXME`, `HACK`, `TEMP`, `XXX`
- `<short description>` is a max-10-word paraphrase of the marker text (not the raw text)
- `<file>` is the filename only (not the full path)
- Keep the whole title under 80 characters

Examples:
```
[tech-debt] FIXME: auth token refresh not handling 401 retry (auth_service.dart)
[tech-debt] HACK: pagination hardcoded to 20 items (feed_repository.dart)
[tech-debt] TODO: migrate deprecated SQLite v1 schema (database_helper.py)
```

## Body format

```markdown
## Tech Debt: <TYPE> in `<file>`

**File:** `<full relative file path>`
**Line:** <line>
**Author:** <author>
**Age:** <age_days> days (<approximate date, e.g. "added ~Jan 2024">)
**Priority score:** <score> (<bucket>)
**File activity:** <file_modifications> commits since marker was added

---

### Marker text

```
<exact marker text from the source>
```

### Why this matters

<1–2 sentences connecting age + activity to actual risk. 
Be specific: "This file has <N> commits since this was added, meaning engineers 
have been working around this issue for <period>."
Do not write generic boilerplate.>

---

*Filed by [tech-debt-agent](https://github.com/shuchitajain/tech-debt-agent). Fingerprint: `<fingerprint>`*
```

## Labels

Always include: `tech-debt`

Add these based on priority:
- High priority → `tech-debt`, `high-priority`
- Medium priority → `tech-debt`
- Low priority → `tech-debt`, `low-priority`

Add these based on type:
- `FIXME` → also add `bug` (if the label exists in the repo)
- `HACK` → also add `tech-debt` only

**Important:** Only use labels that already exist in the repo. If a label doesn't exist, omit it rather than attempting to create it. The `tech-debt` label will be created by init.sh - all others are optional.

## Branch-aware file links

When linking to a specific file+line in the issue body, use:
```
https://github.com/<owner>/<repo>/blob/<branch>/<file>#L<line>
```

Get the current branch by running: `git rev-parse --abbrev-ref HEAD`

Include this as a "View in code" link at the bottom of the issue body before the fingerprint line.
