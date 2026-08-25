"""Structural checks for warehouse DDL (task 1.3)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DDL = REPO_ROOT / "cost_mgmt_etl" / "sql" / "01_ddl.sql"


def _ddl() -> str:
    return DDL.read_text(encoding="utf-8").upper()


def test_ddl_defines_fact_unique_grain() -> None:
    sql = _ddl()
    assert "FACT_OCP_COST_BY_PROJECT" in sql
    for column in (
        "USAGE_DATE",
        "SOURCE_TYPE",
        "CLUSTER_ID",
        "PROJECT",
        "CURRENCY",
        "COST_TOTAL",
        "COST_RAW",
        "COST_MARKUP",
        "COST_USAGE",
        "INFRA_TOTAL",
        "SUPPLEMENTARY_TOTAL",
    ):
        assert column in sql
    assert "UNIQUE" in sql
    assert "USAGE_DATE" in sql and "CLUSTER_ID" in sql
    # Grain order required by spec.
    assert "USAGE_DATE, SOURCE_TYPE, CLUSTER_ID, PROJECT, CURRENCY" in sql.replace("\n", " ").replace("  ", " ")


def test_ddl_includes_watermark_etl_run_and_oracle_types() -> None:
    sql = _ddl()
    assert "WATERMARK" in sql or "ETL_WATERMARK" in sql
    assert "ETL_RUN" in sql
    assert " DATE" in sql or "DATE " in sql
    assert "VARCHAR2" in sql
    assert "NUMBER" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "FREEPDB1" in sql
