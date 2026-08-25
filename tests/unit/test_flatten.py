"""Flatten Cost Management JSON to wide fact rows: zeros, API units, last-wins."""

from __future__ import annotations

from datetime import date

from cost_mgmt_etl.flatten import FactRow, flatten_report


def _leaf(*, total: float, units: str = "BRL", extra: dict | None = None) -> dict:
    payload = {
        "date": "2026-08-10",
        "cost": {
            "total": {"value": total, "units": units},
            "raw": {"value": 0.0, "units": units},
            "markup": {"value": 0.0, "units": units},
            "usage": {"value": 0.0, "units": units},
        },
        "infrastructure": {"total": {"value": 0.0, "units": units}},
        "supplementary": {"total": {"value": 0.0, "units": units}},
    }
    if extra:
        payload.update(extra)
    return payload


def test_flatten_emits_zero_brl_rows_using_api_units() -> None:
    payload = {
        "data": [
            {
                "date": "2026-08-10",
                "projects": [
                    {
                        "project": "openshift-monitoring",
                        "values": [_leaf(total=0.0, units="BRL")],
                    }
                ],
            }
        ]
    }
    rows = flatten_report(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row.usage_date == date(2026, 8, 10)
    assert row.source_type == "openshift"
    assert row.project == "openshift-monitoring"
    assert row.cluster_id == "unknown"
    assert row.currency == "BRL"
    assert row.currency != "USD"
    assert row.cost_total == 0.0
    assert row.cost_raw == 0.0
    assert row.cost_markup == 0.0
    assert row.cost_usage == 0.0
    assert row.infra_total == 0.0
    assert row.supplementary_total == 0.0


def test_flatten_keeps_nonzero_measures_and_cluster_when_present() -> None:
    payload = {
        "data": [
            {
                "date": "2026-08-11",
                "projects": [
                    {
                        "project": "payments",
                        "values": [
                            {
                                "date": "2026-08-11",
                                "clusters": ["cluster-abc"],
                                "cost": {
                                    "total": {"value": 12.5, "units": "BRL"},
                                    "raw": {"value": 10.0, "units": "BRL"},
                                    "markup": {"value": 1.5, "units": "BRL"},
                                    "usage": {"value": 1.0, "units": "BRL"},
                                },
                                "infrastructure": {"total": {"value": 8.0, "units": "BRL"}},
                                "supplementary": {"total": {"value": 4.5, "units": "BRL"}},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    rows = flatten_report(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row.cluster_id == "cluster-abc"
    assert row.cost_total == 12.5
    assert row.cost_raw == 10.0
    assert row.cost_markup == 1.5
    assert row.cost_usage == 1.0
    assert row.infra_total == 8.0
    assert row.supplementary_total == 4.5
    assert row.currency == "BRL"


def test_duplicate_date_project_last_wins_never_sums() -> None:
    payload = {
        "data": [
            {
                "date": "2026-08-10",
                "projects": [
                    {
                        "project": "shared",
                        "values": [
                            _leaf(total=3.0),
                            _leaf(total=5.0),
                        ],
                    }
                ],
            }
        ]
    }
    rows = flatten_report(payload)
    assert len(rows) == 1
    assert rows[0].cost_total == 5.0
    assert rows[0].cost_total != 8.0


def test_flatten_pages_and_unknown_cluster_without_grouping() -> None:
    pages = [
        {
            "data": [
                {
                    "date": "2026-08-01",
                    "projects": [{"project": "alpha", "values": [_leaf(total=0.0)]}],
                }
            ]
        },
        {
            "data": [
                {
                    "date": "2026-08-01",
                    "projects": [{"value": "alpha", "values": [_leaf(total=1.0)]}],
                }
            ]
        },
    ]
    rows = flatten_report(pages, cluster_id_fallback="unknown")
    assert len(rows) == 1
    assert rows[0].project == "alpha"
    assert rows[0].cost_total == 1.0
    assert rows[0].cluster_id == "unknown"


def test_fact_row_grain_matches_warehouse_unique_key() -> None:
    row = FactRow(
        usage_date=date(2026, 8, 10),
        source_type="openshift",
        cluster_id="unknown",
        project="ns",
        currency="BRL",
        cost_total=0.0,
        cost_raw=0.0,
        cost_markup=0.0,
        cost_usage=0.0,
        infra_total=0.0,
        supplementary_total=0.0,
    )
    assert row.grain == (
        date(2026, 8, 10),
        "openshift",
        "unknown",
        "ns",
        "BRL",
    )
