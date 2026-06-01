# IW AI Core — Database Backup & Restore Runbook

This is the operator runbook for the orchestration DB (`iw_orch`) logical
backup subsystem (F-00092). It covers what a backup set contains, how to restore
one safely, the deliberate in-place production swap, identity-pin handling, the
recovery-time expectation, the same-disk storage limitation, and the credential
and version-compatibility constraints.

Backups are **logical** dumps (`pg_dump`/`pg_dumpall`), not physical base
backups. Physical base backups, WAL archiving, and point-in-time recovery (PITR)
are explicitly deferred to a future Tier-2 effort.

> ⚠️ **Agents must not touch backups.** Backup sets contain role password hashes.
> Automated agents MUST NOT read, write, move, or delete anything under
> `IW_CORE_BACKUP_DIR`, and MUST NOT paste backup-set contents into logs,
> reports, or issues. This runbook is for human operators.

---

## What a backup set contains

Each backup is a **timestamped set directory** under `IW_CORE_BACKUP_DIR`
(default `/opt/postgres/data/backups`), named for the UTC instant the backup
started (e.g. `20260601T030000Z/`). The set directory is created `0700`. It
holds exactly three artifacts:

| File | Produced by | Purpose |
|------|-------------|---------|
| `iw_orch.dump` | `pg_dump -Fc` | The `iw_orch` database, PostgreSQL custom format — restore with `pg_restore`. |
| `globals.sql` | `pg_dumpall --globals-only` | Cluster-wide roles **and their password hashes**. Written `0600` (see [Globals file is a secret](#globals-file-is-a-secret)). |
| `manifest.json` | the engine | Metadata about the set (below). |

A backup is only recorded `success` after the engine runs a
`pg_restore --list` integrity check against `iw_orch.dump`. A failed integrity
check (or any error) marks the job `failed`, cleans up the partial set, and —
for scheduled backups — leaves the missed-window catch-up armed for the next
poll.

### Manifest fields

`manifest.json` is pretty-printed JSON with these keys:

| Key | Meaning |
|-----|---------|
| `timestamp_utc` | ISO-8601 UTC instant the backup started. |
| `backup_type` | `scheduled` (daemon) or `manual` (CLI / on-demand). |
| `label` | Optional operator label (manual backups). |
| `alembic_revision` | `alembic_version.version_num` at backup time. |
| `instance_id` | `iw_core_instance` UUID (see [Identity handling](#identity-handling)). |
| `row_counts` | `{projects, batches, work_items}` at backup time — a quick sanity check after restore. |
| `postgres_server_version` | The **source server version** (`SHOW server_version`) — read this to pick a compatible restore client (see [version compatibility](#clientserver-version-compatibility)). |
| `artifacts` | Per-file `{filename, bytes}` for the archive and globals. |

---

## Safe restore (default)

The default and recommended path. `iw db-backup restore` **never** overwrites
the live production DB on 5433 unless you explicitly pass `--allow-prod`; with no
`--target`, it restores into a fresh, non-prod database named
`<IW_CORE_DB_NAME>_restore_<timestamp>` on the configured host, so you can
inspect the result before doing anything irreversible.

```bash
uv run iw db-backup restore --from /opt/postgres/data/backups/20260601T030000Z
# or: ./ai-core.sh db backup-restore --from <set>
```

What it does, in order:

1. **Globals first** — applies `globals.sql` (`psql -f globals.sql` against the
   `postgres` maintenance DB), so the `iw_orch` role and its password exist
   before any owned objects are restored.
2. **Dump** — `pg_restore --clean --if-exists -d <target>` restores `iw_orch.dump`
   into the target database.
3. **Identity check** — runs the `iw db-identity` check against the restored
   target (see [Identity handling](#identity-handling)).
4. **Row counts** — prints `projects` / `batches` / `work_items` counts so you
   can compare against the manifest's `row_counts`.

Restore into a named non-prod DB you control instead of the auto-generated one:

```bash
uv run iw db-backup restore --from <set> --target iw_orch_verify
```

If a step fails, the helper raises with a **copy-pasteable** `psql` / `pg_restore`
command so you can re-run it by hand. (Exit codes: `2` + `REFUSED:` when the
prod-safety guard trips, `1` for other restore errors.)

---

## In-place production swap (deliberate override)

This is the break-glass path used during a real recovery (e.g. after a
displacement incident), where you intentionally rebuild the production cluster
from a backup set. It is **opt-in** — the safety guard refuses it unless you
pass `--allow-prod`.

The clean recovery sequence:

1. **Stand up the production cluster** on its bind mount and bring it up on 5433
   using the I-00122 production path:

   ```bash
   ./ai-core.sh db start-prod        # requires IW_CORE_DB_DATA_DIR in .env
   ```

   `start-prod` starts/creates the raw `iw-orch-pg` container with
   `--restart=always`, binding `${IW_CORE_DB_PORT}:5432` against
   `${IW_CORE_DB_DATA_DIR}`. (See `docs/IW_AI_Core_DB_Setup.md`.)

2. **Apply globals first, then the dump.** Ordering matters: roles/passwords
   must exist before owned objects are restored.

   ```bash
   uv run iw db-backup restore --from <set> --target iw_orch --allow-prod
   ```

   `--allow-prod` is required because `--target` here points at the live
   `IW_CORE_DB_NAME` on the configured host+port — exactly the combination the
   guard blocks by default. Only pass it after you have verified the cluster is
   the intended target and the existing contents are expendable.

3. **Verify**: `./ai-core.sh db status`, then `uv run iw db-identity check`, then
   compare the printed row counts against the set's `manifest.json`.

> Prefer restoring to a non-prod target first and promoting it, when downtime
> budget allows. The in-place swap is for when prod is already lost or being
> rebuilt from scratch.

---

## Identity handling

CR-00014 pins the orchestration DB to an instance fingerprint via
`IW_CORE_EXPECTED_INSTANCE_ID` (see `orch/db/identity.py`). The `iw_core_instance`
row lives inside `iw_orch`, so it **travels inside the logical dump**. A restored
DB therefore keeps the **same `instance_id`** as the source — the existing pin in
`.env` still matches, and `iw db-identity check` reports `match`. No re-pinning is
needed for an ordinary restore of the same database.

The identity check has four modes: `match` (pin set and equal), `mismatch` (pin
set but different — the check exits non-zero), `bootstrap` (no pin set), and
`missing` (no `iw_core_instance` row).

**Re-pinning to a deliberately new identity** — only if you intend the restored
DB to be a *distinct* instance (e.g. a permanent clone running alongside prod):

```bash
uv run iw db-identity show         # prints the live instance_id UUID
# put the printed UUID into .env as:
#   IW_CORE_EXPECTED_INSTANCE_ID=<uuid>
uv run iw db-identity check        # expect: match
```

If you restored to a new identity and the old pin is still in `.env`, the check
will report `mismatch` until you update (or remove) the pin.

---

## Recovery-time expectation (RTO)

At the current orchestration DB size (~1 GB), a logical restore completes in a
matter of **minutes** on local disk — dominated by `pg_restore` rebuilding
indexes, not by I/O. Plan for single-digit minutes of restore time plus the
seconds it takes `./ai-core.sh db start-prod` to bring the cluster up. As the DB
grows, logical-restore time grows roughly with data + index volume; this is one
of the motivations for the deferred Tier-2 physical/PITR work.

---

## Same-disk storage limitation

The default `IW_CORE_BACKUP_DIR=/opt/postgres/data/backups` is a **sibling** of
`pgdata/` (it is *not* inside the live cluster directory) and sits on the **same
disk** as the data.

This is a deliberate trade-off. It protects against the failure modes that
actually keep recurring here:

- operator mistakes and bad migrations,
- **container displacement** — `/opt/postgres/data` is a host bind mount, so
  `docker volume rm` / `docker compose down -v` cannot touch it (the 2026-04-22,
  2026-05-29, and 2026-05-31 displacement incidents; see I-00122 and
  `docs/IW_AI_Core_DB_Setup.md`).

It does **not** protect against:

- physical disk failure, or
- `rm -rf /opt/postgres/data` (or anything that wipes the whole bind mount).

**Moving backups off-host.** The path is configurable precisely so backups can be
relocated. Point `IW_CORE_BACKUP_DIR` at a different filesystem — a separate
disk, an NFS mount, or a mounted object-storage gateway:

```bash
# in .env
IW_CORE_BACKUP_DIR=/mnt/backup-volume/iw_orch
```

Off-host upload to S3/MinIO is the natural Tier-2 extension and uses this same
seam. When you relocate a directory of existing sets, preserve the `0700`/`0600`
permissions (see below).

---

## Globals file is a secret

`pg_dumpall --globals-only` emits role definitions **including password hashes**
(SCRAM/md5) as plaintext SQL. Because the default backup directory is co-located
with the data disk, the engine writes each backup-set directory `0700` and the
`globals.sql` file `0600`, so a co-located backup never widens credential
exposure.

Operator rules:

- **Keep the permissions.** If you copy a backup set elsewhere (off-host,
  another operator's machine), preserve `0700` on the set directory and `0600`
  on `globals.sql` (e.g. `cp -p`, `rsync -a`, `tar --preserve-permissions`).
- **Never paste `globals.sql` into logs, issues, chat, or PRs.** Treat it like a
  credentials file — it effectively is one.
- The security-SAST gate treats the globals file as a secret; do not commit any
  backup artifacts to the repo.

---

## Client/server version compatibility

A restore needs a `pg_restore` / `psql` whose **major version is ≥ the server
version that produced the dump**. `pg_restore` reads newer-format archives with
an equal-or-newer client; an older client against a newer archive fails. (On the
backup side, `pg_dump` likewise refuses to dump from a server **newer** than the
client — which is why the backup engine derives its client image major from the
live server version rather than hardcoding it.)

Read the source server version from the set's manifest:

```bash
python -c "import json,sys; print(json.load(open(sys.argv[1]))['postgres_server_version'])" \
  /opt/postgres/data/backups/20260601T030000Z/manifest.json
# e.g. 15.x
```

Then restore with a matching-or-newer client. If the host has no `psql` /
`pg_restore`, run them from a throwaway client container whose major matches the
recorded version (Linux host networking shown):

```bash
docker run --rm --network host -e PGPASSWORD \
  postgres:15-alpine \
  pg_restore --clean --if-exists -h "$IW_CORE_DB_HOST" -p "$IW_CORE_DB_PORT" \
  -U "$IW_CORE_DB_USER" -d <target> \
  /opt/postgres/data/backups/20260601T030000Z/iw_orch.dump
```

Pick the image tag (`postgres:<major>-alpine`) from the manifest's
`postgres_server_version`, not by guessing.

---

## See also

- `docs/IW_AI_Core_DB_Setup.md` — production vs. bootstrap DB setup, the
  2026-04-22 displacement incident, and `db start-prod` / `IW_CORE_DB_DATA_DIR`.
- `orch/db/identity.py` — the instance-identity fingerprint machinery.
- `CLAUDE.md` — the `IW_CORE_BACKUP_*` config vars and the agents-don't-touch-
  backups rule.
