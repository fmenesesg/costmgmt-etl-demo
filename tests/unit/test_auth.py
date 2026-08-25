"""Auth and settings: fail closed without HCC env; refresh token remaining TTL < 600s."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from cost_mgmt_etl.auth import TOKEN_URL, TokenClient
from cost_mgmt_etl.config import MissingCredentialsError, Settings


def test_missing_client_id_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COSTMGMT_CLIENT_ID", raising=False)
    monkeypatch.setenv("COSTMGMT_CLIENT_SECRET", "present-secret")
    with pytest.raises(MissingCredentialsError, match="COSTMGMT_CLIENT_ID"):
        Settings.from_env()


def test_missing_client_secret_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COSTMGMT_CLIENT_ID", "present-id")
    monkeypatch.delenv("COSTMGMT_CLIENT_SECRET", raising=False)
    with pytest.raises(MissingCredentialsError, match="COSTMGMT_CLIENT_SECRET"):
        Settings.from_env()


def test_token_uses_client_credentials_and_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COSTMGMT_CLIENT_ID", "lab-id")
    monkeypatch.setenv("COSTMGMT_CLIENT_SECRET", "lab-secret")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"access_token": "access-token-1", "expires_in": 900, "token_type": "Bearer"},
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = TokenClient(Settings.from_env(), http=http)
    token = client.get_access_token()
    assert token == "access-token-1"
    assert captured[0].url == httpx.URL(TOKEN_URL)
    assert captured[0].content == b"grant_type=client_credentials&scope=api.console" or (
        "grant_type=client_credentials" in captured[0].content.decode()
        and "scope=api.console" in captured[0].content.decode()
    )
    auth = client.authorization_header()
    assert auth == {"Authorization": "Bearer access-token-1"}


def test_refresh_when_remaining_ttl_below_600_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSTMGMT_CLIENT_ID", "lab-id")
    monkeypatch.setenv("COSTMGMT_CLIENT_SECRET", "lab-secret")
    tokens = iter(["first-token", "refreshed-token"])
    clock = {"now": 0.0}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": next(tokens), "expires_in": 900, "token_type": "Bearer"},
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = TokenClient(
        Settings.from_env(),
        http=http,
        monotonic=lambda: clock["now"],
    )
    assert client.get_access_token() == "first-token"
    clock["now"] = 301.0  # remaining = 900 - 301 = 599 < 600
    assert client.get_access_token() == "refreshed-token"


def test_token_is_not_persisted_to_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("COSTMGMT_CLIENT_ID", "lab-id")
    monkeypatch.setenv("COSTMGMT_CLIENT_SECRET", "lab-secret")
    monkeypatch.chdir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": "ephemeral-token", "expires_in": 900},
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    TokenClient(Settings.from_env(), http=http).get_access_token()
    leftover = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert leftover == []
