"""Start the lab Oracle stack from known files only. Never shell=True."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Compose engine on this host: podman (podman-compose / podman compose). Docker is fallback.
COMPOSE_FILE = "compose.yaml"
DEPLOY_DIR = "deploy"


def compose_engine() -> list[str]:
    if shutil.which("podman"):
        return ["podman", "compose"]
    if shutil.which("podman-compose"):
        return ["podman-compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    return ["podman", "compose"]


def is_allowed_stack_path(raw: str) -> bool:
    if raw == COMPOSE_FILE:
        return True
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        return False
    return (
        len(path.parts) == 2
        and path.parts[0] == DEPLOY_DIR
        and path.suffix == ".yaml"
        and path.name not in {"", ".", ".."}
    )


def stack_command(path: str) -> list[str]:
    if not is_allowed_stack_path(path):
        raise ValueError(f"refusing stack path: {path}")
    if path == COMPOSE_FILE:
        return [*compose_engine(), "-f", COMPOSE_FILE, "up", "-d", "oracle"]
    return ["kubectl", "apply", "-f", path]


def run_stack(path: str, *, runner=subprocess.run) -> int:
    if not is_allowed_stack_path(path):
        return 2
    completed = runner(stack_command(path), check=False, shell=False)
    return int(completed.returncode)


def lab_rollback_steps() -> list[str]:
    """Stop the lab container and drop oracle-data. SaaS Cost Management is unchanged."""
    engine = compose_engine()
    return [
        " ".join([*engine, "-f", COMPOSE_FILE, "down", "-v"]),
        "SaaS Cost Management is unchanged; only the local oracle-data volume is dropped.",
    ]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    target = args[0] if args else COMPOSE_FILE
    return run_stack(target)


if __name__ == "__main__":
    raise SystemExit(main())
