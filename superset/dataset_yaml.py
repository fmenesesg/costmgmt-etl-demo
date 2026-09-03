"""Parse Class A dataset YAML without a YAML dependency."""

from __future__ import annotations

from pathlib import Path


def dataset_name(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip()
    raise ValueError(f"missing name in {path}")


def dataset_sql(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    _, _, rest = text.partition("sql: |")
    if not rest:
        raise ValueError(f"missing sql: | block in {path}")
    lines: list[str] = []
    for line in rest.splitlines():
        if line.startswith("  "):
            lines.append(line[2:])
        elif line.strip():
            break
    sql = "\n".join(lines).strip()
    if not sql:
        raise ValueError(f"empty sql in {path}")
    return sql
