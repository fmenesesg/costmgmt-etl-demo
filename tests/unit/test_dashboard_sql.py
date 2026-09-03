"""Structural checks for Class A warehouse dataset SQL (profile bi)."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "superset" / "datasets"
FACT_DATASETS = ("supplementary", "infra", "cost_total")
GRAIN_KEYS = ("usage_date", "source_type", "cluster_id", "project")


def _dataset_text(name: str) -> str:
    path = DATASET_DIR / f"{name}.yaml"
    assert path.is_file(), f"missing dataset file {path}"
    return path.read_text(encoding="utf-8")


def _collapsed(sql: str) -> str:
    return " ".join(sql.lower().split())


def test_fact_datasets_filter_brl_and_group_remaining_grain() -> None:
    for name in FACT_DATASETS:
        text = _dataset_text(name)
        collapsed = _collapsed(text)
        assert "fact_ocp_cost_by_project" in collapsed
        assert "currency = 'brl'" in collapsed
        assert "group by" in collapsed
        for key in GRAIN_KEYS:
            assert key in collapsed
            assert key in collapsed.split("group by", 1)[1]
        assert "infinity" not in collapsed
        assert "cost explorer" not in collapsed


def test_layer_datasets_never_add_cost_total() -> None:
    supplementary = _collapsed(_dataset_text("supplementary"))
    infra = _collapsed(_dataset_text("infra"))
    assert "sum(supplementary_total)" in supplementary.replace(" ", "")
    assert "cost_total" not in supplementary
    assert "sum(infra_total)" in infra.replace(" ", "")
    assert "cost_total" not in infra
    assert "infra_total <> 0" not in infra
    assert "infra_total != 0" not in infra
    assert "infra_total > 0" not in infra


def test_cost_total_dataset_sums_cost_total_alone() -> None:
    text = _collapsed(_dataset_text("cost_total"))
    assert "sum(cost_total)" in text.replace(" ", "")
    assert "supplementary_total" not in text
    assert "infra_total" not in text
    assert "+" not in text.split("select", 1)[1].split("from", 1)[0]


def test_watermark_uses_etl_job_and_does_not_invent_totals() -> None:
    text = _collapsed(_dataset_text("watermark"))
    assert "etl_watermark" in text
    assert "ocp_cost_by_project" in text
    assert "sum(" not in text
    assert "cost_total" not in text
    assert "supplementary_total" not in text
    assert "infra_total" not in text
    assert "coalesce" not in text


def test_bootstrap_avoids_unregistered_nvd3_viz_types() -> None:
    text = (REPO_ROOT / "superset" / "bootstrap_dashboards.py").read_text(encoding="utf-8")
    assert '"viz_type": "dist_bar"' not in text
    assert ",\n            \"dist_bar\"" not in text
    assert '"viz_type": "bar"' not in text
    assert '"viz_type": "echarts_timeseries_bar"' in text
    assert '"viz_type": "big_number_total"' in text
    assert '"viz_type": "table"' in text


def test_dataset_yaml_parser_reads_name_and_sql() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "superset"))
    from dataset_yaml import dataset_name, dataset_sql

    path = DATASET_DIR / "supplementary.yaml"
    assert dataset_name(path) == "supplementary_by_project"
    sql = dataset_sql(path)
    assert "SUM(supplementary_total)" in sql
    assert "currency = 'BRL'" in sql


def test_optional_lab_oracle_thin_connection_skips_when_oracle_down() -> None:
    import socket

    try:
        socket.create_connection(("127.0.0.1", 1521), timeout=2).close()
    except OSError as exc:
        pytest.skip(f"Oracle down: localhost:1521 connection refused ({exc})")
    oracledb = pytest.importorskip("oracledb")
    conn = oracledb.connect(
        user="costmgmt",
        password="OracleDemo1",
        dsn="localhost:1521/FREEPDB1",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM dual")
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()
