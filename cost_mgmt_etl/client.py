"""Paginated Cost Management OpenShift cost extract with month-bounded windows."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Protocol

import httpx

from cost_mgmt_etl.config import PAGE_LIMIT, REPORTS_URL, Settings

__all__ = [
    "REPORTS_URL",
    "CostManagementError",
    "CostReportsClient",
    "month_bounds",
]


class CostManagementError(RuntimeError):
    """Extract failed; callers MUST treat the job as unsuccessful."""


class TokenSource(Protocol):
    def authorization_header(self) -> dict[str, str]: ...


def month_bounds(year: int, month: int, *, today: date | None = None) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    if today is not None and today.year == year and today.month == month:
        end = min(end, today)
    return start, end


def _leaf_count(payload: dict[str, Any]) -> int:
    total = 0
    for bucket in payload.get("data") or []:
        total += len(bucket.get("projects") or [])
        total += len(bucket.get("clusters") or [])
    return total


def _is_group_by_limit(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    body = response.text or ""
    if "check_group_by_limit" in body:
        return True
    try:
        payload = response.json()
    except ValueError:
        return False
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if not isinstance(errors, list):
        return False
    return any(
        isinstance(item, dict) and item.get("code") == "check_group_by_limit" for item in errors
    )


class CostReportsClient:
    def __init__(
        self,
        settings: Settings,
        *,
        token: TokenSource,
        http: httpx.Client,
    ) -> None:
        self._settings = settings
        self._token = token
        self._http = http
        self.cluster_id_fallback: str | None = None

    def fetch_month(
        self, year: int, month: int, *, today: date | None = None
    ) -> list[dict[str, Any]]:
        start, end = month_bounds(year, month, today=today)
        use_cluster = True
        self.cluster_id_fallback = None
        offset = 0
        pages: list[dict[str, Any]] = []
        while True:
            response = self._get_page(start, end, offset, use_cluster=use_cluster)
            if use_cluster and _is_group_by_limit(response):
                use_cluster = False
                self.cluster_id_fallback = "unknown"
                continue
            if response.status_code >= 400:
                raise CostManagementError(
                    f"report page failed with HTTP {response.status_code}: {response.text}"
                )
            payload = response.json()
            pages.append(payload)
            if _leaf_count(payload) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
        return pages

    def _get_page(
        self, start: date, end: date, offset: int, *, use_cluster: bool
    ) -> httpx.Response:
        params: dict[str, str] = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "filter[resolution]": "daily",
            "filter[limit]": str(PAGE_LIMIT),
            "filter[offset]": str(offset),
            "group_by[project]": "*",
        }
        if use_cluster:
            params["group_by[cluster]"] = "*"
        last_429: httpx.Response | None = None
        for _attempt in range(2):
            response = self._http.get(
                REPORTS_URL,
                params=params,
                headers=self._token.authorization_header(),
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
            if response.status_code == 429:
                last_429 = response
                continue
            return response
        raise CostManagementError(
            f"429 after retry: {last_429.text if last_429 is not None else ''}"
        )
