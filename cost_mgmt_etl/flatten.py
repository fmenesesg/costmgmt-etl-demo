"""Flatten Cost Management report JSON to wide last-wins fact rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

from cost_mgmt_etl.config import SOURCE_TYPE_OPENSHIFT


@dataclass(frozen=True)
class FactRow:
    usage_date: date
    source_type: str
    cluster_id: str
    project: str
    currency: str
    cost_total: float
    cost_raw: float
    cost_markup: float
    cost_usage: float
    infra_total: float
    supplementary_total: float

    @property
    def grain(self) -> tuple[date, str, str, str, str]:
        return (
            self.usage_date,
            self.source_type,
            self.cluster_id,
            self.project,
            self.currency,
        )


def last_wins(rows: Iterable[FactRow]) -> list[FactRow]:
    collapsed: dict[tuple[date, str, str, str, str], FactRow] = {}
    for row in rows:
        collapsed[row.grain] = row
    return list(collapsed.values())


def flatten_report(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    cluster_id_fallback: str = "unknown",
) -> list[FactRow]:
    pages: Sequence[Mapping[str, Any]]
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, Mapping)):
        pages = payload
    else:
        pages = [payload]  # type: ignore[list-item]
    rows: list[FactRow] = []
    for page in pages:
        rows.extend(_flatten_page(page, cluster_id_fallback=cluster_id_fallback))
    return last_wins(rows)


def _flatten_page(page: Mapping[str, Any], *, cluster_id_fallback: str) -> list[FactRow]:
    rows: list[FactRow] = []
    for bucket in page.get("data") or []:
        bucket_date = bucket.get("date")
        for project_entry in bucket.get("projects") or []:
            project_name = _project_name(project_entry)
            if not project_name:
                continue
            for leaf, cluster_name in _iter_leaves(project_entry):
                fallback = cluster_name or cluster_id_fallback
                rows.append(
                    _row_from_leaf(
                        leaf,
                        project_entry=project_entry,
                        project_name=project_name,
                        bucket_date=bucket_date,
                        cluster_id_fallback=fallback,
                    )
                )
    return rows


def _iter_leaves(
    project_entry: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], str | None]]:
    """Yield cost leaves from project.values or nested project.clusters[].values."""
    direct = [item for item in (project_entry.get("values") or []) if isinstance(item, Mapping)]
    if direct:
        return [(leaf, None) for leaf in direct]
    leaves: list[tuple[Mapping[str, Any], str | None]] = []
    for cluster_entry in project_entry.get("clusters") or []:
        if not isinstance(cluster_entry, Mapping):
            continue
        raw_cluster = cluster_entry.get("cluster") or cluster_entry.get("value")
        cluster_name = str(raw_cluster) if raw_cluster not in (None, "") else None
        for leaf in cluster_entry.get("values") or []:
            if isinstance(leaf, Mapping):
                leaves.append((leaf, cluster_name))
    return leaves


def _project_name(project_entry: Mapping[str, Any]) -> str:
    raw = project_entry.get("project")
    if raw in (None, ""):
        raw = project_entry.get("value")
    return str(raw) if raw not in (None, "") else ""


def _row_from_leaf(
    leaf: Mapping[str, Any],
    *,
    project_entry: Mapping[str, Any],
    project_name: str,
    bucket_date: Any,
    cluster_id_fallback: str,
) -> FactRow:
    usage = leaf.get("date") or bucket_date
    units = _currency_units(leaf)
    return FactRow(
        usage_date=date.fromisoformat(str(usage)[:10]),
        source_type=SOURCE_TYPE_OPENSHIFT,
        cluster_id=_cluster_id(leaf, project_entry, cluster_id_fallback),
        project=project_name,
        currency=units,
        cost_total=_measure(leaf, "cost", "total"),
        cost_raw=_measure(leaf, "cost", "raw"),
        cost_markup=_measure(leaf, "cost", "markup"),
        cost_usage=_measure(leaf, "cost", "usage"),
        infra_total=_measure(leaf, "infrastructure", "total"),
        supplementary_total=_measure(leaf, "supplementary", "total"),
    )


def _measure(leaf: Mapping[str, Any], layer: str, field: str) -> float:
    node: Any = leaf.get(layer)
    if isinstance(node, Mapping):
        node = node.get(field)
    if isinstance(node, Mapping):
        node = node.get("value", 0.0)
    if node is None:
        return 0.0
    return float(node)


def _currency_units(leaf: Mapping[str, Any]) -> str:
    for layer, field in (
        ("cost", "total"),
        ("cost", "raw"),
        ("infrastructure", "total"),
        ("supplementary", "total"),
    ):
        node: Any = leaf.get(layer)
        if isinstance(node, Mapping):
            node = node.get(field)
        if isinstance(node, Mapping):
            units = node.get("units")
            if isinstance(units, str) and units:
                return units
    return ""


def _cluster_id(
    leaf: Mapping[str, Any],
    project_entry: Mapping[str, Any],
    fallback: str,
) -> str:
    for key in ("cluster", "cluster_id"):
        value = leaf.get(key)
        if isinstance(value, str) and value:
            return value
    clusters = leaf.get("clusters")
    if isinstance(clusters, list) and clusters:
        first = clusters[0]
        if isinstance(first, Mapping):
            return str(first.get("cluster") or first.get("value") or fallback)
        return str(first)
    for key in ("cluster", "cluster_id"):
        value = project_entry.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback
