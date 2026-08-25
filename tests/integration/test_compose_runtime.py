"""Compose runtime: password override, restart durability, lab DSN, mocked HCC."""

from __future__ import annotations

import os
import subprocess
import time
from datetime import date
from pathlib import Path

import pytest

from cost_mgmt_etl.flatten import FactRow
from cost_mgmt_etl.jobs import JOB_NAME, run_daily_job
from cost_mgmt_etl.load import merge_facts
from tests.integration.oracle_fixtures import LAB_DSN, oracle_connect_kwargs

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTAINER = "costmanagement_oracle_1"
CUSTOMER_HOST_MARKERS = ("oracle.corp", "customer.example", "prod-oracle", "adw.")


def _compose_config(extra_env: dict[str, str]) -> str:
    env = {**os.environ, **extra_env}
    for engine in (
        ["podman-compose", "config"],
        ["podman", "compose", "config"],
        ["docker", "compose", "config"],
    ):
        try:
            result = subprocess.run(
                engine,
                cwd=REPO_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    pytest.fail("no compose engine produced config output")


def test_lab_dsn_is_localhost_not_customer_host() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "localhost:1521/FREEPDB1" in example
    assert "oracle:1521/FREEPDB1" in compose
    for text in (compose, example):
        for marker in CUSTOMER_HOST_MARKERS:
            assert marker not in text
    kwargs = oracle_connect_kwargs()
    assert kwargs["dsn"] == LAB_DSN


def test_env_overrides_compose_app_user_password() -> None:
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "${APP_USER_PASSWORD:-OracleDemo1}" in compose
    rendered = _compose_config({"APP_USER_PASSWORD": "OverridePass1"})
    assert "OverridePass1" in rendered
    assert "OracleDemo1" in compose


def test_hcc_is_mocked_during_job(oracle_conn) -> None:
    def extract_pages(start: date, end: date):
        return [
            {
                "data": [
                    {
                        "date": start.isoformat(),
                        "projects": [
                            {
                                "project": "mocked-hcc",
                                "values": [
                                    {
                                        "date": start.isoformat(),
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

    result = run_daily_job(
        oracle_conn,
        extract_pages=extract_pages,
        run_on=date(2026, 8, 20),
        job_name=f"{JOB_NAME}_mocked",
    )
    assert result.status == "success"
    with oracle_conn.cursor() as cur:
        cur.execute(
            "SELECT currency, cost_total FROM fact_ocp_cost_by_project WHERE project = 'mocked-hcc'"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "BRL"
    assert float(row[1]) == 0.0


def test_restart_durability_keeps_merged_row(oracle_conn) -> None:
    marker = FactRow(
        usage_date=date(2026, 1, 15),
        source_type="openshift",
        cluster_id="unknown",
        project="durability-marker",
        currency="BRL",
        cost_total=0.0,
        cost_raw=0.0,
        cost_markup=0.0,
        cost_usage=0.0,
        infra_total=0.0,
        supplementary_total=0.0,
    )
    merge_facts(oracle_conn, [marker], run_id=9001)
    restarted = subprocess.run(
        ["podman", "restart", CONTAINER],
        check=False,
        capture_output=True,
        text=True,
    )
    assert restarted.returncode == 0, restarted.stderr
    deadline = time.time() + 120
    while time.time() < deadline:
        inspect = subprocess.run(
            ["podman", "inspect", CONTAINER, "--format", "{{.State.Health.Status}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if inspect.stdout.strip() == "healthy":
            break
        time.sleep(2)
    else:
        pytest.fail("Oracle container did not return to healthy after restart")

    import oracledb

    kwargs = oracle_connect_kwargs()
    conn = oracledb.connect(user=kwargs["user"], password=kwargs["password"], dsn=kwargs["dsn"])
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cost_total, currency
                FROM fact_ocp_cost_by_project
                WHERE project = 'durability-marker'
                  AND usage_date = DATE '2026-01-15'
                """
            )
            row = cur.fetchone()
    finally:
        conn.close()
    assert row is not None
    assert float(row[0]) == 0.0
    assert row[1] == "BRL"
