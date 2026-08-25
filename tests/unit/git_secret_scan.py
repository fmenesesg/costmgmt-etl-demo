"""Scan a working tree for HCC credential literals and production-looking Oracle passwords."""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".cursor",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"}

HCC_ASSIGNMENT = re.compile(
    r"^(?P<hcc_key>COSTMGMT_CLIENT_(?:ID|SECRET))=(?P<hcc_value>[^\n]*)$",
    re.MULTILINE,
)
ORACLE_ASSIGNMENT = re.compile(
    r"^(?P<ora_key>ORACLE_PASSWORD|APP_USER_PASSWORD|ORACLE_PWD)=(?P<ora_value>[^\n]*)$",
    re.MULTILINE,
)
ALLOWED_ORACLE_PLACEHOLDERS = {
    "",
    "OracleDemo1",
}
ENV_SUBSTITUTION = re.compile(r"^\$\{[A-Z0-9_]+(?::-[^}]*)?\}$")


def _is_skipped_dir(path: Path) -> bool:
    return path.name in SKIP_DIR_NAMES


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _hcc_value_forbidden(value: str) -> bool:
    cleaned = _strip_quotes(value)
    if cleaned == "" or ENV_SUBSTITUTION.match(cleaned):
        return False
    if cleaned.endswith(":-}"):
        return False
    return True


def _oracle_value_forbidden(value: str) -> bool:
    cleaned = _strip_quotes(value)
    if cleaned in ALLOWED_ORACLE_PLACEHOLDERS:
        return False
    if ENV_SUBSTITUTION.match(cleaned):
        return False
    return True


def find_secret_findings(root: Path) -> list[str]:
    """Return human-readable findings. Empty list means the tree is clean."""
    findings: list[str] = []
    for path in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        for match in HCC_ASSIGNMENT.finditer(text):
            key, raw = match.group("hcc_key"), match.group("hcc_value")
            if _hcc_value_forbidden(raw):
                findings.append(f"{rel}: forbidden HCC assignment {key}={_strip_quotes(raw)}")
        for match in ORACLE_ASSIGNMENT.finditer(text):
            key, raw = match.group("ora_key"), match.group("ora_value")
            if _oracle_value_forbidden(raw):
                findings.append(
                    f"{rel}: production-looking Oracle password assignment {key}={_strip_quotes(raw)}"
                )
    return findings
