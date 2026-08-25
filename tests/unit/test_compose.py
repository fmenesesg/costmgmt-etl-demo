"""Structural checks for the lab Oracle Compose stack (task 1.2)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compose_uses_gvenzl_oracle_free_slim_not_faststart() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "gvenzl/oracle-free:23.26.2-slim" in compose
    assert "faststart" not in compose
    assert "1521:1521" in compose
    assert "APP_USER" in compose and "costmgmt" in compose
    assert "oracle-data" in compose
    assert "healthcheck" in compose
    assert "healthcheck.sh" in compose
    assert "profiles:" in compose and "etl" in compose
    assert "ORACLE_DSN" in compose
    assert "oracle:1521/FREEPDB1" in compose
    etl_block = compose.split("etl:")[-1]
    assert "oracle:1521/FREEPDB1" in etl_block
    assert "localhost:1521/FREEPDB1" not in etl_block
