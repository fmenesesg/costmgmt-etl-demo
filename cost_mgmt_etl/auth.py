"""OAuth2 client_credentials token source. Tokens stay in memory only."""

from __future__ import annotations

import time
from typing import Callable

import httpx

from cost_mgmt_etl.config import TOKEN_REFRESH_SKEW_SECONDS, TOKEN_URL, Settings

__all__ = ["TOKEN_URL", "TokenClient"]


class TokenClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http: httpx.Client,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._http = http
        self._monotonic = monotonic
        self._access_token: str | None = None
        self._expires_at = 0.0

    def get_access_token(self) -> str:
        remaining = self._expires_at - self._monotonic()
        if self._access_token is None or remaining < TOKEN_REFRESH_SKEW_SECONDS:
            self._refresh()
        assert self._access_token is not None
        return self._access_token

    def authorization_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_access_token()}"}

    def _refresh(self) -> None:
        response = self._http.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "scope": "api.console",
                "client_id": self._settings.client_id,
                "client_secret": self._settings.client_secret,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = str(payload["access_token"])
        expires_in = float(payload.get("expires_in", 900))
        self._expires_at = self._monotonic() + expires_in
