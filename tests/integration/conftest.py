"""Shared Oracle connection for warehouse integration tests."""

from tests.integration.oracle_fixtures import LAB_DSN, oracle_conn, oracle_connect_kwargs

__all__ = ["LAB_DSN", "oracle_conn", "oracle_connect_kwargs"]
