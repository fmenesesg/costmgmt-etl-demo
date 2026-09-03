"""Run the daily job or a multi-month backfill against lab Oracle."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import httpx
import oracledb

from cost_mgmt_etl.auth import TokenClient
from cost_mgmt_etl.client import CostReportsClient
from cost_mgmt_etl.config import Settings
from cost_mgmt_etl.jobs import backfill_run_dates, run_daily_job

DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"

USAGE = (
    "usage: python -m cost_mgmt_etl run\n"
    "       python -m cost_mgmt_etl backfill [months]\n"
    "       python -m cost_mgmt_etl compose.yaml\n"
    "Requires COSTMGMT_CLIENT_ID and COSTMGMT_CLIENT_SECRET; uses ORACLE_* for the warehouse.\n"
)


def load_project_dotenv(path: Path | None = None) -> None:
    """Load gitignored .env without overriding variables already in the process."""
    env_path = DOTENV_PATH if path is None else path
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _extract_pages(client: CostReportsClient, today: date):
    def extract_pages(start: date, end: date):
        return client.fetch_month(start.year, start.month, today=today)

    return extract_pages


def _connect(settings: Settings):
    return oracledb.connect(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=settings.oracle_dsn,
    )


def run_extract(kind: str, *, months: int = 4, today: date | None = None) -> list[str]:
    load_project_dotenv()
    settings = Settings.from_env()
    today = today or date.today()
    statuses: list[str] = []
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True) as http:
        token = TokenClient(settings, http=http)
        client = CostReportsClient(settings, token=token, http=http)
        connection = _connect(settings)
        try:
            run_dates = [today] if kind == "run" else backfill_run_dates(today, months=months)
            for run_on in run_dates:
                result = run_daily_job(
                    connection,
                    extract_pages=_extract_pages(client, today),
                    run_on=run_on,
                )
                statuses.append(f"{run_on.isoformat()}:{result.status}:{result.run_id}")
        finally:
            connection.close()
    return statuses


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] not in {"run", "backfill"}:
        sys.stdout.write(USAGE)
        return 0 if not args else 2
    kind = args[0]
    months = 4
    if kind == "backfill" and len(args) > 1:
        try:
            months = int(args[1])
        except ValueError:
            sys.stdout.write(USAGE)
            return 2
        if months < 1:
            sys.stdout.write(USAGE)
            return 2
    load_project_dotenv()
    statuses = run_extract(kind, months=months)
    sys.stdout.write("\n".join(statuses) + "\n")
    return 0
