# Release Notes Template

Use this template when generating release notes. Replace all `{placeholders}`.

---

```markdown
# InnoForge {version}

<!-- generated: {YYYY-MM-DD} -->

**Release Date**: {YYYY-MM-DD}
**Previous Version**: {previous-version}

## Highlights

{2-3 sentence summary of the most important changes in this release. Written for a non-technical audience who wants to know "what's new and why should I care."}

## New Features

{For each `feat` commit, one bullet point with a human-readable description. Group related commits.}

- **{Feature title}**: {One sentence description of what users can now do.} ({commit scope})

## Improvements

{For each non-breaking `refactor`, `perf`, or enhancement commit.}

- **{Improvement title}**: {One sentence.} ({commit scope})

## Bug Fixes

{For each `fix` commit.}

- **{Bug title}**: {What was broken and how it's fixed.} ({commit scope})

## Breaking Changes

{For any commits with `BREAKING CHANGE` footer or `!` in type. If none, omit this section entirely.}

- **{Change}**: {What changed, why, and what users need to do.}

## Migration Guide

{Only include if there are breaking changes or database migrations. Otherwise omit.}

### Database Migrations

{List Alembic migrations included in this release.}

```bash
alembic upgrade head
```

### Configuration Changes

{New or changed environment variables / system_config keys.}

| Key | Change | Action Required |
|-----|--------|-----------------|
| `{key}` | {Added/Changed/Removed} | {What the user needs to do} |

## Dependencies

{Only include if notable dependency changes. Otherwise omit.}

- Added: {package} {version}
- Updated: {package} {old} → {new}
- Removed: {package}

## Full Changelog

See [CHANGELOG.md](../CHANGELOG.md) for the complete list of commits.
```
