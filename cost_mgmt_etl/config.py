"""Runtime settings from environment. HCC credentials fail closed when missing."""

from __future__ import annotations

import os
from dataclasses import dataclass

TOKEN_URL = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
REPORTS_URL = "https://console.redhat.com/api/cost-management/v1/reports/openshift/costs/"
LAB_ORACLE_DSN = "localhost:1521/FREEPDB1"
COMPOSE_ORACLE_DSN = "oracle:1521/FREEPDB1"
TOKEN_REFRESH_SKEW_SECONDS = 600
PAGE_LIMIT = 100
SOURCE_TYPE_OPENSHIFT = "openshift"


class MissingCredentialsError(RuntimeError):
    """Raised when HCC service-account environment variables are unset."""


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    oracle_dsn: str = LAB_ORACLE_DSN
    oracle_user: str = "costmgmt"
    oracle_password: str = "OracleDemo1"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ
        client_id = (env.get("COSTMGMT_CLIENT_ID") or "").strip()
        client_secret = (env.get("COSTMGMT_CLIENT_SECRET") or "").strip()
        missing: list[str] = []
        if not client_id:
            missing.append("COSTMGMT_CLIENT_ID")
        if not client_secret:
            missing.append("COSTMGMT_CLIENT_SECRET")
        if missing:
            raise MissingCredentialsError(
                "Missing required HCC credentials: " + ", ".join(missing)
            )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            oracle_dsn=env.get("ORACLE_DSN") or LAB_ORACLE_DSN,
            oracle_user=env.get("ORACLE_USER") or "costmgmt",
            oracle_password=env.get("ORACLE_PASSWORD")
            or env.get("APP_USER_PASSWORD")
            or "OracleDemo1",
        )
