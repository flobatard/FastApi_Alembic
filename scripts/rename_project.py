"""
Rename a project created from the template.

Updates the package name (pyproject.toml + uv.lock), the API title
(PROJECT_NAME), the README title and the PostgreSQL database name
(app/core/config.py, config/*.yaml, docker-compose.yml).

Usage: scripts/rename.sh "My Project" [--slug ...] [--db ...] [--description ...] [--dry-run]

Re-runnable: current values are located by pattern rather than assumed, and
no file is written if any pattern is missing.
"""

import argparse
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Normalized package name (PEP 503) and unquoted PostgreSQL identifier.
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DB_RE = re.compile(r"[a-z_][a-z0-9_]{0,62}")


@dataclass(frozen=True)
class Rule:
    """Replace whatever follows the prefix captured by `pattern` (group 1) with `value`."""

    path: str
    pattern: str
    value: str
    count: int = 0  # 0 = every occurrence, 1 = first one only


def slugify(name: str, sep: str) -> str:
    """'Mon Projet Élevé' -> 'mon-projet-eleve' (sep='-') or 'mon_projet_eleve' (sep='_')."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", sep, ascii_name.lower()).strip(sep)


def quoted(value: str) -> str:
    """Double-quoted literal, valid in both Python and TOML (value checked by `plain_text`)."""
    return f'"{value}"'


def plain_text(value: str) -> bool:
    """No quote, backslash or newline: the value can be written without any escaping."""
    return not any(char in value for char in '"\\\n')


def build_rules(name: str, slug: str, db: str, description: str | None) -> list[Rule]:
    rules = [
        Rule("pyproject.toml", r'^(name = )".*"$', quoted(slug), count=1),
        Rule("app/core/config.py", r'^([ \t]*PROJECT_NAME: str = )".*"$', quoted(name)),
        Rule("app/core/config.py", r'^([ \t]*POSTGRES_DB: str = )".*"$', quoted(db)),
        Rule("config/development.yaml", r"^(POSTGRES_DB: ).*$", db),
        Rule("config/production.yaml", r"^(POSTGRES_DB: ).*$", db),
        Rule("docker-compose.yml", r"(\$\{POSTGRES_DB:-)[^}]*(?=\})", db),
        Rule("README.md", r"^(# ).*$", name, count=1),
    ]
    if description is not None:
        rules.append(
            Rule("pyproject.toml", r'^(description = )".*"$', quoted(description), count=1)
        )
    return rules


def substitute(rule: Rule, text: str) -> tuple[str, int]:
    return re.subn(
        rule.pattern,
        lambda m: m.group(1) + rule.value,
        text,
        count=rule.count,
        flags=re.MULTILINE,
    )


def apply(rules: list[Rule]) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Compute the new content of each file without writing anything."""
    originals: dict[str, str] = {}
    errors: list[str] = []
    for path in dict.fromkeys(rule.path for rule in rules):
        try:
            originals[path] = (ROOT / path).read_text(encoding="utf-8")
        except FileNotFoundError:
            errors.append(f"{path}: file not found")

    updated = dict(originals)
    for rule in rules:
        if rule.path not in updated:
            continue
        updated[rule.path], matches = substitute(rule, updated[rule.path])
        if matches == 0:
            errors.append(f"{rule.path}: pattern {rule.pattern!r} not found")
    return originals, updated, errors


def changed_lines(before: str, after: str) -> list[tuple[int, str, str]]:
    pairs = zip(before.splitlines(), after.splitlines(), strict=True)
    return [(i, old, new) for i, (old, new) in enumerate(pairs, 1) if old != new]


def dotenv_overrides() -> list[str]:
    """Keys in .env that would override the renamed database name."""
    dotenv = ROOT / ".env"
    if not dotenv.is_file():
        return []
    keys = {
        line.split("=", 1)[0].strip()
        for line in dotenv.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    return sorted(keys & {"POSTGRES_DB", "DATABASE_URL"})


def refresh_lockfile() -> None:
    if shutil.which("uv") is None:
        print("uv not found: run `uv lock` to update uv.lock.", file=sys.stderr)
    elif subprocess.run(["uv", "lock"], cwd=ROOT).returncode != 0:
        print("`uv lock` failed: run it again manually.", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename a project created from the template.")
    parser.add_argument("name", help='display name of the project, e.g. "My Project"')
    parser.add_argument("--slug", help="package name (pyproject.toml); default: derived from name")
    parser.add_argument("--db", help="PostgreSQL database name; default: derived from name")
    parser.add_argument("--description", help="package description; unchanged if omitted")
    parser.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    args = parser.parse_args()

    name = args.name.strip()
    if not name or not plain_text(name):
        parser.error('name must be non-empty, single-line, without " or \\')
    if args.description is not None and not plain_text(args.description):
        parser.error('description must be single-line, without " or \\')
    slug = args.slug or slugify(name, "-")
    if not SLUG_RE.fullmatch(slug):
        parser.error(f"invalid slug {slug!r}: lowercase letters, digits and dashes (use --slug)")
    db = args.db or slugify(name, "_")
    if not DB_RE.fullmatch(db):
        parser.error(f"invalid database name {db!r}: [a-z_][a-z0-9_]*, max 63 chars (use --db)")

    originals, updated, errors = apply(build_rules(name, slug, db, args.description))
    if errors:
        print("\n".join(errors), "No file modified.", sep="\n", file=sys.stderr)
        return 1

    changes = {path: changed_lines(originals[path], text) for path, text in updated.items()}
    if not any(changes.values()):
        print("Nothing to change: the project already has this name.")
        return 0
    for path, lines in changes.items():
        for lineno, old, new in lines:
            print(f"{path}:{lineno}\n  - {old.strip()}\n  + {new.strip()}")

    if args.dry_run:
        print("\n(dry run: no file modified)")
        return 0

    for path, lines in changes.items():
        if lines:
            (ROOT / path).write_text(updated[path], encoding="utf-8")
    if changes["pyproject.toml"]:
        refresh_lockfile()

    print(f"\nRenamed to {name!r} (package {slug}, database {db}).")
    if any("POSTGRES_DB" in old for lines in changes.values() for _, old, _ in lines):
        for key in dotenv_overrides():
            print(f"- .env sets {key}: update it by hand.")
        print(
            "- Local Postgres: create the new database with scripts/init.sh.\n"
            "- Docker: an already-initialized pgdata volume keeps the old database (the\n"
            "  postgres image only creates POSTGRES_DB on first start): `docker compose down -v`\n"
            "  if its data is disposable."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
