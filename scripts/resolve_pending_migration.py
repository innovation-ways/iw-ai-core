from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

DOWN_REVISION_PATTERN = re.compile(
    r"^(down_revision(?:\s*:\s*[^=\n]+)?\s*=\s*)(.+)$",
    re.MULTILINE,
)
REVISION_PATTERN = re.compile(
    r"^\s*revision(?:\s*:\s*[^=\n]+)?\s*=\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
DOWN_PARSE_PATTERN = re.compile(
    r"^\s*down_revision(?:\s*:\s*[^=\n]+)?\s*=\s*([^\s#]+)",
    re.MULTILINE,
)


def _strip_quotes(value: str) -> str:
    is_double = value[0] == '"' and value[-1] == '"'
    is_single = value[0] == "'" and value[-1] == "'"
    if len(value) >= 2 and (is_double or is_single):
        return value[1:-1]
    return value


def _parse_migration(path: Path) -> tuple[str, str | tuple[str, ...] | None]:
    content = path.read_text(encoding="utf-8")

    revision_match = REVISION_PATTERN.search(content)
    if not revision_match:
        raise ValueError(f"could not parse revision in {path}")
    revision = revision_match.group(1)

    tree = ast.parse(content)
    for node in tree.body:
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "down_revision":
                    value_node = node.value
                    break
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "down_revision"
        ):
            value_node = node.value

        if value_node is None:
            continue

        value = ast.literal_eval(value_node)
        if value is None or isinstance(value, str):
            return revision, value
        if isinstance(value, tuple) and all(isinstance(v, str) for v in value):
            return revision, tuple(value)
        raise ValueError(f"unsupported down_revision value in {path}: {value!r}")

    down_match = DOWN_PARSE_PATTERN.search(content)
    if not down_match:
        raise ValueError(f"could not parse down_revision in {path}")

    raw_down = down_match.group(1)
    if raw_down == "None":
        return revision, None
    return revision, _strip_quotes(raw_down)


def _rewrite_down_revision(path: Path, replacement_literal: str) -> None:
    content = path.read_text(encoding="utf-8")

    def _replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{replacement_literal}"

    rewritten, count = DOWN_REVISION_PATTERN.subn(_replace, content, count=1)
    if count == 0:
        raise ValueError(f"could not find down_revision line in {path}")

    path.write_text(rewritten, encoding="utf-8")


def resolve_pending_migration(versions_dir: Path) -> list[tuple[str, str | None]]:
    migrations: list[tuple[Path, str, str | tuple[str, ...] | None]] = []
    for path in sorted(versions_dir.glob("*.py")):
        if "__pycache__" in path.parts:
            continue
        revision, down_revision = _parse_migration(path)
        migrations.append((path, revision, down_revision))

    pending = [(path, revision) for path, revision, down in migrations if down == "PENDING"]
    if not pending:
        return []

    real_migrations = [
        (revision, down) for _path, revision, down in migrations if down != "PENDING"
    ]

    real_revisions = {revision for revision, _down in real_migrations}
    pointed_to: set[str] = set()
    for _revision, down in real_migrations:
        if down is None:
            continue
        if isinstance(down, tuple):
            pointed_to.update(down)
            continue
        pointed_to.add(down)

    real_heads = sorted(real_revisions - pointed_to)
    if len(real_heads) > 1:
        heads = ", ".join(real_heads)
        raise RuntimeError(f"multiple real migration heads detected: {heads}")

    current_head = real_heads[0] if real_heads else None
    replacement_literal = f'"{current_head}"' if current_head is not None else "None"

    rewrites: list[tuple[str, str | None]] = []
    for path, revision in pending:
        _rewrite_down_revision(path, replacement_literal)
        rewrites.append((revision, current_head))

    return rewrites


def main() -> int:
    versions_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("orch/db/migrations/versions")

    if not versions_dir.exists() or not versions_dir.is_dir():
        sys.stderr.write(f"Error: versions directory not found: {versions_dir}\n")
        return 1

    try:
        rewrites = resolve_pending_migration(versions_dir)
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1

    if not rewrites:
        sys.stdout.write("no PENDING migrations found — nothing to do\n")
        return 0

    summary = ", ".join(
        f"{revision} → {new_down if new_down is not None else 'None'}"
        for revision, new_down in rewrites
    )
    sys.stdout.write(f"Resolved {len(rewrites)} PENDING migration(s): {summary}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
