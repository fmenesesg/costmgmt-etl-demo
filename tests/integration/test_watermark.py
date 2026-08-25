"""Watermark and etl_run fail-closed behavior (task 3.2)."""

from __future__ import annotations

from datetime import date

import pytest

from cost_mgmt_etl.client import CostManagementError
from cost_mgmt_etl.jobs import JOB_NAME, extract_windows, run_daily_job


def test_daily_windows_include_current_month() -> None:
    windows = extract_windows(date(2026, 8, 25))
    assert (date(2026, 8, 1), date(2026, 8, 25)) in windows
    assert all(start.month == end.month for start, end in windows)


def test_day_two_includes_previous_month_and_other_days_do_not() -> None:
    day_two = extract_windows(date(2026, 8, 2))
    assert (date(2026, 8, 1), date(2026, 8, 2)) in day_two
    assert (date(2026, 7, 1), date(2026, 7, 31)) in day_two
    day_three = extract_windows(date(2026, 8, 3))
    assert (date(2026, 7, 1), date(2026, 7, 31)) not in day_three
    assert (date(2026, 8, 1), date(2026, 8, 3)) in day_three


def test_success_advances_watermark_and_records_etl_run(oracle_conn) -> None:
    pages = [
        {
            "data": [
                {
                    "date": "2026-08-01",
                    "projects": [
                        {
                            "project": "wm-success",
                            "values": [
                                {
                                    "date": "2026-08-01",
                                    "cost": {
                                        "total": {"value": 0.0, "units": "BRL"},
                                        "raw": {"value": 0.0, "units": "BRL"},
                                        "markup": {"value": 0.0, "units": "BRL"},
                                        "usage": {"value": 0.0, "units": "BRL"},
                                    },
                                    "infrastructure": {"total": {"value": 0.0, "units": "BRL"}},
                                    "supplementary": {"total": {"value": 0.0, "units": "BRL"}},
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    ]

    def extract_pages(start: date, end: date):
        return pages

    result = run_daily_job(
        oracle_conn,
        extract_pages=extract_pages,
        run_on=date(2026, 8, 15),
        job_name=JOB_NAME,
    )
    assert result.status == "success"
    with oracle_conn.cursor() as cur:
        cur.execute(
            "SELECT last_success_end FROM etl_watermark WHERE job_name = :n",
            {"n": JOB_NAME},
        )
        wm = cur.fetchone()
        cur.execute(
            """
            SELECT status FROM etl_run
            WHERE etl_run_id = :id
            """,
            {"id": result.run_id},
        )
        run_row = cur.fetchone()
    assert wm is not None
    assert wm[0].date() == date(2026, 8, 15) or wm[0] == date(2026, 8, 15)
    assert run_row[0] == "success"


def test_failed_page_does_not_advance_watermark(oracle_conn) -> None:
    with oracle_conn.cursor() as cur:
        cur.execute(
            """
            MERGE INTO etl_watermark t
            USING (SELECT :n job_name FROM dual) s
            ON (t.job_name = s.job_name)
            WHEN MATCHED THEN UPDATE SET t.last_success_end = DATE '2026-07-31'
            WHEN NOT MATCHED THEN INSERT (job_name, last_success_end, updated_at)
            VALUES (:n, DATE '2026-07-31', SYSTIMESTAMP)
            """,
            {"n": JOB_NAME},
        )
    oracle_conn.commit()

    def extract_pages(start: date, end: date):
        raise CostManagementError("429 after retry: failed page")

    with pytest.raises(CostManagementError, match="429"):
        run_daily_job(
            oracle_conn,
            extract_pages=extract_pages,
            run_on=date(2026, 8, 15),
            job_name=JOB_NAME,
        )
    with oracle_conn.cursor() as cur:
        cur.execute(
            "SELECT last_success_end FROM etl_watermark WHERE job_name = :n",
            {"n": JOB_NAME},
        )
        wm = cur.fetchone()
        cur.execute(
            """
            SELECT status FROM etl_run
            WHERE job_name = :n
            ORDER BY etl_run_id DESC FETCH FIRST 1 ROW ONLY
            """,
            {"n": JOB_NAME},
        )
        run_row = cur.fetchone()
    assert wm[0].date() == date(2026, 7, 31) or wm[0] == date(2026, 7, 31)
    assert run_row[0] == "failed"
