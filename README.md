# IW AI Core Platform

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache-2.0-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/innovation-ways/IW AI Core Platform/badge)](https://securityscorecards.dev/viewer/?uri=github.com/innovation-ways/IW AI Core Platform)




Maintained by [Innovation Ways](https://innovation-ways.com).

---

## Overview

<!-- TODO: 2-4 paragraphs explaining what the project does, why it exists, and who should use it. -->

## Installation

<!-- TODO: Installation instructions per supported environment. Examples below. -->

```bash
# Python (pip)
pip install IW AI Core Platform

# Python (uv)
uv add IW AI Core Platform

# From source
git clone https://github.com/innovation-ways/IW AI Core Platform.git
cd IW AI Core Platform
# ... build/install steps
```

## Usage

<!-- TODO: Minimal working example. Show what a user types and what they get back. -->

```bash
IW AI Core Platform --help
```

## Database backups

The orchestration database has a built-in logical backup subsystem. The daemon
takes a **daily scheduled** backup (with missed-window catch-up after downtime),
and operators can take **on-demand** backups at any time — even with the daemon
stopped. Each backup set is a `pg_dump -Fc` archive of `iw_orch`, a
`pg_dumpall --globals-only` SQL file (roles + passwords), and a JSON manifest,
verified with a `pg_restore --list` integrity check.

```bash
uv run iw db-backup create --label pre-migration   # on-demand backup now
uv run iw db-backup list                            # list recorded backups
uv run iw db-backup prune                           # apply retention now
uv run iw db-backup restore --from <set>            # guided restore (safe non-prod target)

# equivalent ./ai-core.sh wrappers
./ai-core.sh db backup --label pre-migration
./ai-core.sh db backup-list
./ai-core.sh db backup-prune
./ai-core.sh db backup-restore --from <set>
```

Behavior is configured in `.env`: `IW_CORE_BACKUP_ENABLED` (default `true`),
`IW_CORE_BACKUP_DIR` (default `/opt/postgres/data/backups`),
`IW_CORE_BACKUP_RETENTION_DAYS` (default `30`), and `IW_CORE_BACKUP_TIME`
(daily, default `03:00`). Scheduled backups older than the retention window are
pruned automatically; manual/labeled backups are kept indefinitely.

See the [restore runbook](docs/IW_AI_Core_DB_Backup_Restore.md) for how to
restore a backup set, the same-disk storage limitation, and how to move backups
off-host.

## Documentation

<!-- TODO: Link to full docs if hosted; otherwise link to key docs/ files. -->

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to open issues and pull requests.

All commits must be signed-off per the [Developer Certificate of Origin](https://developercertificate.org/):

```bash
git commit -s -m "your message"
```

## Code of Conduct

This project adopts the [Contributor Covenant v3](CODE_OF_CONDUCT.md). By participating, you agree to abide by its terms. Report concerns to info@innovation-ways.com.

## Security

Please do not file public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for our reporting process.

## License

This project is licensed under the [Apache-2.0](LICENSE) license.

Copyright © 2026 .

## Trademark

"Innovation Ways" are trademarks of . See [TRADEMARK.md](TRADEMARK.md) for permitted uses.
