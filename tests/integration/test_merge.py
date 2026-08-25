"""Idempotent last-wins MERGE of 0.0 BRL fact rows (task 3.1)."""

from __future__ import annotations

from datetime import date

from cost_mgmt_etl.flatten import FactRow
from cost_mgmt_etl.load import MERGE_SQL, merge_facts


def _row(*, total: float, project: str = "openshift-monitoring") -> FactRow:
    return FactRow(
        usage_date=date(2026, 8, 10),
        source_type="openshift",
        cluster_id="unknown",
        project=project,
        currency="BRL",
        cost_total=total,
        cost_raw=0.0,
        cost_markup=0.0,
        cost_usage=0.0,
        infra_total=0.0,
        supplementary_total=0.0,
    )


def test_merge_sql_is_last_wins_six_measures_not_sum() -> None:
    sql = " ".join(MERGE_SQL.split())
    assert "MERGE INTO" in sql.upper()
    assert "FACT_OCP_COST_BY_PROJECT" in sql.upper()
    for column in (
        "cost_total",
        "cost_raw",
        "cost_markup",
        "cost_usage",
        "infra_total",
        "supplementary_total",
    ):
        assert column in sql
    assert "SUM(" not in sql.upper()
    assert "WHEN MATCHED THEN UPDATE SET" in sql.upper()
    assert "t.cost_total = s.cost_total" in sql.lower().replace(" ", "") or (
        "t.cost_total=s.cost_total" in sql.lower().replace(" ", "")
    )


def test_idempotent_merge_persists_zero_brl_once(oracle_conn) -> None:
    merge_facts(oracle_conn, [_row(total=0.0)], run_id=101)
    merge_facts(oracle_conn, [_row(total=0.0)], run_id=102)
    with oracle_conn.cursor() as cur:
        cur.execute(
            """
            SELECT cost_total, currency, COUNT(*) OVER () AS n
            FROM fact_ocp_cost_by_project
            WHERE usage_date = DATE '2026-08-10'
              AND project = 'openshift-monitoring'
              AND cluster_id = 'unknown'
              AND currency = 'BRL'
            """
        )
        rows = cur.fetchall()
    assert len(rows) == 1
    cost_total, currency, n = rows[0]
    assert float(cost_total) == 0.0
    assert currency == "BRL"
    assert int(n) == 1


def test_batch_duplicate_grain_last_wins_never_sums(oracle_conn) -> None:
    merge_facts(
        oracle_conn,
        [_row(total=3.0, project="shared"), _row(total=5.0, project="shared")],
        run_id=103,
    )
    with oracle_conn.cursor() as cur:
        cur.execute(
            """
            SELECT cost_total
            FROM fact_ocp_cost_by_project
            WHERE usage_date = DATE '2026-08-10'
              AND project = 'shared'
              AND currency = 'BRL'
            """
        )
        rows = cur.fetchall()
    assert len(rows) == 1
    assert float(rows[0][0]) == 5.0
    assert float(rows[0][0]) != 8.0
