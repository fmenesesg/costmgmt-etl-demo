"""Daily extract windows, etl_run audit, and fail-closed watermark."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from cost_mgmt_etl.client import month_bounds
from cost_mgmt_etl.flatten import flatten_report
from cost_mgmt_etl.load import merge_facts

JOB_NAME = "ocp_cost_by_project"


@dataclass(frozen=True)
class JobResult:
    run_id: int
    status: str


def extract_windows(run_on: date) -> list[tuple[date, date]]:
    """Current month (covers daily overlap) plus previous month on day 2."""
    windows = [month_bounds(run_on.year, run_on.month, today=run_on)]
    if run_on.day == 2:
        previous = run_on.replace(day=1) - timedelta(days=1)
        windows.append(month_bounds(previous.year, previous.month, today=previous))
    return windows


def run_daily_job(
    connection,
    *,
    extract_pages: Callable[[date, date], list[dict]],
    run_on: date,
    job_name: str = JOB_NAME,
) -> JobResult:
    windows = extract_windows(run_on)
    window_start = min(start for start, _end in windows)
    window_end = max(end for _start, end in windows)
    run_id = _insert_run(connection, job_name, window_start, window_end)
    try:
        rows = []
        for start, end in windows:
            pages = extract_pages(start, end)
            rows.extend(flatten_report(pages, cluster_id_fallback="unknown"))
        merge_facts(connection, rows, run_id=run_id)
        _advance_watermark(connection, job_name, window_end, run_id)
        _finish_run(connection, run_id, "success", rows_in=len(rows), rows_upserted=len(rows))
        return JobResult(run_id=run_id, status="success")
    except Exception as exc:
        _finish_run(connection, run_id, "failed", error=str(exc))
        raise


def _insert_run(connection, job_name: str, window_start: date, window_end: date) -> int:
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl_run (job_name, window_start, window_end, status, started_at)
            VALUES (:job_name, :window_start, :window_end, 'running', SYSTIMESTAMP)
            """,
            {
                "job_name": job_name,
                "window_start": window_start,
                "window_end": window_end,
            },
        )
        cur.execute(
            """
            SELECT etl_run_id FROM etl_run
            WHERE job_name = :job_name
            ORDER BY etl_run_id DESC FETCH FIRST 1 ROW ONLY
            """,
            {"job_name": job_name},
        )
        run_id = int(cur.fetchone()[0])
    connection.commit()
    return run_id


def _finish_run(
    connection,
    run_id: int,
    status: str,
    *,
    error: str | None = None,
    rows_in: int | None = None,
    rows_upserted: int | None = None,
) -> None:
    with connection.cursor() as cur:
        cur.execute(
            """
            UPDATE etl_run
               SET status = :status,
                   finished_at = SYSTIMESTAMP,
                   error_message = :error_message,
                   rows_in = :rows_in,
                   rows_upserted = :rows_upserted
             WHERE etl_run_id = :run_id
            """,
            {
                "status": status,
                "error_message": error,
                "rows_in": rows_in,
                "rows_upserted": rows_upserted,
                "run_id": run_id,
            },
        )
    connection.commit()


def _advance_watermark(connection, job_name: str, window_end: date, run_id: int) -> None:
    with connection.cursor() as cur:
        cur.execute(
            """
            MERGE INTO etl_watermark t
            USING (
                SELECT :job_name job_name,
                       :last_success_end last_success_end,
                       :run_id last_success_run_id
                FROM dual
            ) s
            ON (t.job_name = s.job_name)
            WHEN MATCHED THEN UPDATE SET
                t.last_success_end = s.last_success_end,
                t.last_success_run_id = s.last_success_run_id,
                t.updated_at = SYSTIMESTAMP
            WHEN NOT MATCHED THEN INSERT (
                job_name, last_success_end, last_success_run_id, updated_at
            ) VALUES (
                s.job_name, s.last_success_end, s.last_success_run_id, SYSTIMESTAMP
            )
            """,
            {
                "job_name": job_name,
                "last_success_end": window_end,
                "run_id": run_id,
            },
        )
    connection.commit()
