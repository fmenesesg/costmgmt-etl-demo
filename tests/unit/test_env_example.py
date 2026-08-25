"""Structural checks for env templates (task 1.4)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _assignment(text: str, key: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith(f"{key}="):
            return stripped.split("=", 1)[1]
    raise AssertionError(f"{key} assignment missing")


def test_env_example_has_empty_hcc_keys_and_lab_oracle_placeholder() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert _assignment(example, "COSTMGMT_CLIENT_ID") == ""
    assert _assignment(example, "COSTMGMT_CLIENT_SECRET") == ""
    assert _assignment(example, "ORACLE_PASSWORD") == "OracleDemo1"
    assert _assignment(example, "APP_USER_PASSWORD") == "OracleDemo1"
    assert _assignment(example, "ORACLE_USER") == "costmgmt"
    assert _assignment(example, "ORACLE_DSN") == "localhost:1521/FREEPDB1"
    assert "COSTMGMT_CLIENT_SECRET=" in example
    secret_value = _assignment(example, "COSTMGMT_CLIENT_SECRET")
    assert secret_value == ""


def test_gitignore_ignores_dotenv() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    names = {line.strip() for line in gitignore.splitlines() if line.strip() and not line.strip().startswith("#")}
    assert ".env" in names
