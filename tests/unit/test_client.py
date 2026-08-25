"""Month-bounded Cost Management report extract (never daily -90)."""

from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from cost_mgmt_etl.client import (
    REPORTS_URL,
    CostManagementError,
    CostReportsClient,
    month_bounds,
)
from cost_mgmt_etl.config import Settings


class _StubToken:
    def authorization_header(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-token"}


def _settings() -> Settings:
    return Settings(client_id="id", client_secret="secret")


def _client(handler) -> CostReportsClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return CostReportsClient(_settings(), token=_StubToken(), http=http)


def test_month_bounds_are_calendar_month_not_rolling_90() -> None:
    start, end = month_bounds(2026, 7, today=date(2026, 8, 25))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 7, 31)
    current_start, current_end = month_bounds(2026, 8, today=date(2026, 8, 25))
    assert current_start == date(2026, 8, 1)
    assert current_end == date(2026, 8, 25)


def test_extract_uses_month_dates_limit_100_and_never_time_scope_minus_90() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"data": [], "meta": {"count": 0}})

    pages = _client(handler).fetch_month(2026, 8, today=date(2026, 8, 15))
    assert pages == [{"data": [], "meta": {"count": 0}}]
    assert captured, "extract must issue at least one GET"
    request = captured[0]
    assert str(request.url).startswith(REPORTS_URL)
    params = parse_qs(urlparse(str(request.url)).query)
    assert params["start_date"] == ["2026-08-01"]
    assert params["end_date"] == ["2026-08-15"]
    assert params["filter[resolution]"] == ["daily"]
    assert params["filter[limit]"] == ["100"]
    assert params["filter[offset]"] == ["0"]
    assert params["group_by[project]"] == ["*"]
    assert params["group_by[cluster]"] == ["*"]
    assert request.headers["Authorization"] == "Bearer test-token"
    for item in captured:
        query = urlparse(str(item.url)).query
        assert "time_scope_value" not in query
        assert "-90" not in query


def test_paginates_with_offset_until_short_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = parse_qs(urlparse(str(request.url)).query)
        offset = int(params["filter[offset]"][0])
        if offset == 0:
            return httpx.Response(
                200,
                json={"data": [{"date": "2026-08-01", "projects": [{}] * 100}]},
            )
        if offset == 100:
            return httpx.Response(
                200,
                json={"data": [{"date": "2026-08-02", "projects": [{}] * 3}]},
            )
        raise AssertionError(f"unexpected offset {offset}")

    pages = _client(handler).fetch_month(2026, 8, today=date(2026, 8, 15))
    assert len(pages) == 2
    assert len(pages[0]["data"][0]["projects"]) == 100
    assert len(pages[1]["data"][0]["projects"]) == 3


def test_429_retries_once_then_fails() -> None:
    statuses: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        statuses.append(429)
        return httpx.Response(429, json={"error": "rate limited"}, headers={"Retry-After": "0"})

    with pytest.raises(CostManagementError, match="429"):
        _client(handler).fetch_month(2026, 8, today=date(2026, 8, 15))
    assert len(statuses) == 2


def test_429_then_success_on_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"data": [{"date": "2026-08-01"}]})

    pages = _client(handler).fetch_month(2026, 8, today=date(2026, 8, 15))
    assert pages[0]["data"][0]["date"] == "2026-08-01"
    assert calls["n"] == 2


def test_dual_group_by_rejected_falls_back_to_project_only() -> None:
    seen_cluster: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = parse_qs(urlparse(str(request.url)).query)
        has_cluster = "group_by[cluster]" in params
        seen_cluster.append(has_cluster)
        if has_cluster:
            return httpx.Response(
                400,
                json={"errors": [{"code": "check_group_by_limit", "detail": "too many group_by"}]},
            )
        return httpx.Response(200, json={"data": [{"date": "2026-08-01", "projects": []}]})

    client = _client(handler)
    pages = client.fetch_month(2026, 8, today=date(2026, 8, 15))
    assert True in seen_cluster and False in seen_cluster
    assert client.cluster_id_fallback == "unknown"
    assert pages[0]["data"][0]["date"] == "2026-08-01"
