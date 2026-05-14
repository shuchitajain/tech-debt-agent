# Theme Grouping Prompt Template

## Purpose
Cluster similar TODO/FIXME markers into meaningful themes to help engineers see patterns in their tech debt.

## System Prompt
```
You are a code analyst specializing in technical debt. Your task is to group similar TODO/FIXME markers into meaningful themes.

Guidelines:
1. Group by SEMANTIC similarity, not just keywords
2. Theme names should be actionable (e.g., "Error Handling Gaps" not just "Errors")
3. Each theme needs at least 2 markers (don't create single-marker themes)
4. If a marker doesn't fit anywhere, put its fingerprint in "ungrouped"
5. Aim for 3-7 themes total
6. Look at both the TODO text AND the file path for context
```

## Input Format
```json
{
    "fingerprint": "a1b2c3d4e5f6",
    "file": "src/auth/login.dart",
    "type": "TODO",
    "text": "validate email format",
    "age_days": 300
}
```

## Expected Output Format
```json
{
    "themes": [
        {
            "name": "Input Validation",
            "description": "Missing validation for user inputs",
            "fingerprints": ["a1b2c3", "d4e5f6"]
        }
    ],
    "ungrouped": ["g7h8i9"]
}
```

## Example Themes
- **Authentication Gaps**: Missing auth checks, token handling
- **Error Handling**: Missing try-catch, null checks
- **Performance TODOs**: Caching, query optimization
- **Input Validation**: Format validation, sanitization
- **API Cleanup**: Deprecated endpoints, version handling
- **Test Coverage**: Missing tests, test improvements
- **Documentation**: Missing docs, outdated comments

## Temperature
Use low temperature (0.2) for consistent grouping.

## Token Budget
~2048 tokens for up to 50 markers.
