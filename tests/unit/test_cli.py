"""CLI wiring: fail closed without HCC env; backfill covers last N months."""

import os
from datetime import date
from pathlib import Path

import pytest

from cost_mgmt_etl.cli import main as cli_main
from cost_mgmt_etl.config import MissingCredentialsError
from cost_mgmt_etl.jobs import backfill_run_dates


def test_backfill_run_dates_last_four_months_capped_at_today() -> None:
    dates = backfill_run_dates(date(2026, 9, 1), months=4)
    assert dates == [
        date(2026, 6, 30),
        date(2026, 7, 31),
        date(2026, 8, 31),
        date(2026, 9, 1),
    ]


def test_cli_run_fails_closed_without_hcc_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("cost_mgmt_etl.cli.DOTENV_PATH", tmp_path / "missing.env")
    monkeypatch.delenv("COSTMGMT_CLIENT_ID", raising=False)
    monkeypatch.delenv("COSTMGMT_CLIENT_SECRET", raising=False)
    with pytest.raises(MissingCredentialsError):
        cli_main(["run"])


def test_cli_run_loads_dotenv_then_invokes_extract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COSTMGMT_CLIENT_ID=from-dotenv-id\nCOSTMGMT_CLIENT_SECRET=from-dotenv-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("cost_mgmt_etl.cli.DOTENV_PATH", env_file)
    monkeypatch.delenv("COSTMGMT_CLIENT_ID", raising=False)
    monkeypatch.delenv("COSTMGMT_CLIENT_SECRET", raising=False)
    captured: list[str] = []
    monkeypatch.setattr(
        "cost_mgmt_etl.cli.run_extract",
        lambda kind, months=4, today=None: captured.append(kind) or ["2026-09-01:success:1"],
    )
    assert cli_main(["run"]) == 0
    assert captured == ["run"]
    assert os.environ["COSTMGMT_CLIENT_ID"] == "from-dotenv-id"
    assert os.environ["COSTMGMT_CLIENT_SECRET"] == "from-dotenv-secret"


def test_cli_unknown_job_command_returns_usage_code() -> None:
    assert cli_main(["explode"]) == 2
