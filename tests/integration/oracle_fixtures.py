"""Shared Oracle connection for warehouse integration tests."""

from __future__ import annotations

import os

import pytest

LAB_DSN = "localhost:1521/FREEPDB1"


def oracle_connect_kwargs() -> dict[str, str]:
    return {
        "user": os.environ.get("ORACLE_USER", "costmgmt"),
        "password": os.environ.get("ORACLE_PASSWORD")
        or os.environ.get("APP_USER_PASSWORD", "OracleDemo1"),
        "dsn": os.environ.get("ORACLE_DSN", LAB_DSN),
    }


@pytest.fixture
def oracle_conn():
    oracledb = pytest.importorskip("oracledb")
    kwargs = oracle_connect_kwargs()
    assert kwargs["dsn"] == LAB_DSN, "integration tests use lab DSN localhost:1521/FREEPDB1 only"
    try:
        conn = oracledb.connect(user=kwargs["user"], password=kwargs["password"], dsn=kwargs["dsn"])
    except Exception as exc:  # pragma: no cover - environment
        pytest.fail(f"Oracle at {LAB_DSN} is not reachable: {exc}")
    try:
        yield conn
    finally:
        conn.close()
