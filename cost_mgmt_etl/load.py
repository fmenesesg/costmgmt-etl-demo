"""Thin-mode Oracle MERGE for FACT_OCP_COST_BY_PROJECT (Policy A last-wins)."""

from __future__ import annotations

from typing import Iterable

from cost_mgmt_etl.flatten import FactRow, last_wins

MERGE_SQL = """
MERGE INTO fact_ocp_cost_by_project t
USING (
    SELECT
        :usage_date AS usage_date,
        :source_type AS source_type,
        :cluster_id AS cluster_id,
        :project AS project,
        :currency AS currency,
        :cost_total AS cost_total,
        :cost_raw AS cost_raw,
        :cost_markup AS cost_markup,
        :cost_usage AS cost_usage,
        :infra_total AS infra_total,
        :supplementary_total AS supplementary_total,
        :etl_run_id AS etl_run_id
    FROM dual
) s
ON (
    t.usage_date = s.usage_date
    AND t.source_type = s.source_type
    AND t.cluster_id = s.cluster_id
    AND t.project = s.project
    AND t.currency = s.currency
)
WHEN MATCHED THEN UPDATE SET
    t.cost_total = s.cost_total,
    t.cost_raw = s.cost_raw,
    t.cost_markup = s.cost_markup,
    t.cost_usage = s.cost_usage,
    t.infra_total = s.infra_total,
    t.supplementary_total = s.supplementary_total,
    t.extracted_at = SYSTIMESTAMP,
    t.etl_run_id = s.etl_run_id
WHEN NOT MATCHED THEN INSERT (
    usage_date, source_type, cluster_id, project, currency,
    cost_total, cost_raw, cost_markup, cost_usage, infra_total, supplementary_total,
    extracted_at, etl_run_id
) VALUES (
    s.usage_date, s.source_type, s.cluster_id, s.project, s.currency,
    s.cost_total, s.cost_raw, s.cost_markup, s.cost_usage, s.infra_total,
    s.supplementary_total, SYSTIMESTAMP, s.etl_run_id
)
"""


def connect_thin(*, user: str, password: str, dsn: str):
    import oracledb

    return oracledb.connect(user=user, password=password, dsn=dsn)


def merge_facts(connection, rows: Iterable[FactRow], *, run_id: int) -> int:
    collapsed = last_wins(rows)
    if not collapsed:
        return 0
    with connection.cursor() as cur:
        for row in collapsed:
            cur.execute(
                MERGE_SQL,
                {
                    "usage_date": row.usage_date,
                    "source_type": row.source_type,
                    "cluster_id": row.cluster_id,
                    "project": row.project,
                    "currency": row.currency,
                    "cost_total": row.cost_total,
                    "cost_raw": row.cost_raw,
                    "cost_markup": row.cost_markup,
                    "cost_usage": row.cost_usage,
                    "infra_total": row.infra_total,
                    "supplementary_total": row.supplementary_total,
                    "etl_run_id": run_id,
                },
            )
    connection.commit()
    return len(collapsed)
