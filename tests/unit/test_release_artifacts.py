"""Task 4.3: pins file is not a stack executable; CronJob env names only; lab rollback docs."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_requirements_txt_is_pin_file_not_stack_executable() -> None:
    text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "not a stack executable" in text.lower() or "NOT a stack executable" in text
    assert "oracledb==" in text
    assert "httpx==" in text
    assert "pytest==" in text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            assert "==" in stripped, f"pin required: {stripped}"


def test_cronjob_uses_env_names_and_secret_refs_only() -> None:
    text = (REPO_ROOT / "deploy" / "cronjob.yaml").read_text(encoding="utf-8")
    assert "name: COSTMGMT_CLIENT_ID" in text
    assert "name: COSTMGMT_CLIENT_SECRET" in text
    assert "secretKeyRef" in text
    assert "COSTMGMT_CLIENT_SECRET=" not in text
    assert "OracleDemo1" not in text
    inline_values = [
        line.split("value:", 1)[1].strip()
        for line in text.splitlines()
        if line.strip().startswith("value:") and not line.strip().startswith("valueFrom:")
    ]
    assert "oracle:1521/FREEPDB1" in inline_values
    assert "costmgmt" in inline_values
    assert all("password" not in value.lower() for value in inline_values)


def test_readme_documents_lab_rollback_and_compose_engine() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "oracle-data" in text
    assert "SaaS" in text and "unchanged" in text.lower()
    assert "podman" in text.lower()
    assert "down" in text.lower() or "stop" in text.lower()


def test_architecture_doc_has_incremental_ingestion_anchor() -> None:
    text = (REPO_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert 'id="incremental-ingestion"' in text
    assert "[Incremental ingestion](#incremental-ingestion)" in text


def test_readme_links_to_architecture_incremental_ingestion() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/architecture.md#incremental-ingestion" in text


def test_readme_documents_bi_profile_uri_brl_and_rollback_without_oracle_volume() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "--profile bi" in text
    assert "oracle+oracledb://costmgmt:${APP_USER_PASSWORD}@oracle:1521/?service_name=FREEPDB1" in text
    assert "BRL" in text
    assert "Infinity" in text
    assert "podman-compose --profile bi down" in text
    assert "down -v" in text
    assert "superset-home" in text

