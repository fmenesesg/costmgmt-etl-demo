"""Structural checks for the lab Oracle Compose stack (task 1.2)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _service_block(compose: str, name: str) -> str:
    lines = compose.splitlines()
    header = f"  {name}:"
    start = None
    for i, line in enumerate(lines):
        if line == header or line.startswith(header + " "):
            start = i
            break
    if start is None:
        raise AssertionError(f"missing compose service {name!r}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.startswith("volumes:") and not line.startswith(" "):
            end = j
            break
        if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            end = j
            break
    return "\n".join(lines[start:end])


def _section_entries(block: str, section: str) -> list[str]:
    entries: list[str] = []
    in_section = False
    for line in block.splitlines():
        if line.startswith("    ") and not line.startswith("     "):
            key = line.strip().split(":", 1)[0]
            if in_section and key != section:
                break
            in_section = key == section
            continue
        if in_section and line.startswith("      "):
            item = line.strip()
            if item.startswith("- "):
                entries.append(item[2:].strip())
            elif ":" in item:
                entries.append(item.split(":", 1)[0])
    return entries


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


def test_compose_superset_uses_bi_profile_pinned_image_localhost_and_volume() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    superset = _service_block(compose, "superset")
    assert "profiles:" in superset
    assert _section_entries(superset, "profiles") == ["bi"]
    assert "docker.io/apache/superset:6.1.0" in superset
    assert "127.0.0.1:8088:8088" in superset
    assert "superset-home" in superset
    assert "superset-home:" in compose
    depends = _section_entries(superset, "depends_on")
    assert "oracle" in depends
    oracle = _service_block(compose, "oracle")
    assert "profiles:" not in oracle


def test_compose_superset_env_is_lab_oracle_only_without_hcc() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    superset = _service_block(compose, "superset")
    env_keys = _section_entries(superset, "environment")
    assert env_keys == ["APP_USER_PASSWORD", "SUPERSET_SECRET_KEY"]
    assert "COSTMGMT" not in superset
    etl = _service_block(compose, "etl")
    assert "COSTMGMT_CLIENT_ID" in etl
    assert "COSTMGMT_CLIENT_SECRET" in etl


def test_compose_superset_command_installs_oracledb_inits_and_seeds_dashboard() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    superset = _service_block(compose, "superset")
    assert "command:" in superset
    assert "pip" in superset and "oracledb" in superset
    assert "PYTHONPATH" in superset
    assert "superset_home/.local/lib/python3.10/site-packages" in superset
    assert "db upgrade" in superset
    assert "create-admin" in superset
    assert "|| true" in superset
    assert "init" in superset
    assert "bootstrap_dashboards.py" in superset
    assert "run-server" in superset
    assert "bootstrap.sh" not in compose
    assert "ojdbc" not in compose
    assert "ojdbc" not in superset
    etl = _service_block(compose, "etl")
    assert "cost_mgmt_etl backfill" in etl
    assert "pip install -r requirements.txt" in etl


def test_superset_config_aliases_oracledb_and_uses_sqlite_metadata() -> None:
    path = REPO_ROOT / "superset" / "superset_config.py"
    assert path.is_file(), f"missing {path}"
    config = path.read_text(encoding="utf-8")
    assert 'sys.modules["cx_Oracle"]' in config or "sys.modules['cx_Oracle']" in config
    assert "oracle.oracledb" in config
    assert "cx_oracle" in config
    assert "sqlite:////app/superset_home/superset.db" in config
    assert "SUPERSET_SECRET_KEY" in config
    assert "TALISMAN_ENABLED" in config
    assert "False" in config
    assert "init_oracle_client" not in config
    assert "ojdbc" not in config
