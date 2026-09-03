"""Idempotent lab seed: Oracle DB, Class A datasets, charts, and a published dashboard."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dataset_yaml import dataset_name, dataset_sql

DATASET_DIR = Path("/app/pythonpath/datasets")
DASHBOARD_SLUG = "ocp-cost-warehouse"
DATABASE_NAME = "Lab Oracle Cost Management"
URI_TEMPLATE = (
    "oracle+oracledb://costmgmt:{password}@oracle:1521/?service_name=FREEPDB1"
)
DATASET_FILES = ("supplementary", "infra", "cost_total", "watermark")

# Populated after Flask create_app() — importing models earlier raises.
db = None
User = None
Database = None
SqlaTable = None
Slice = None
Dashboard = None


def _load_superset_models() -> None:
    global db, User, Database, SqlaTable, Slice, Dashboard
    from flask_appbuilder.security.sqla.models import User as FabUser
    from superset import db as superset_db
    from superset.connectors.sqla.models import SqlaTable as Dataset
    from superset.models.core import Database as CoreDatabase
    from superset.models.dashboard import Dashboard as Dash
    from superset.models.slice import Slice as Chart

    db = superset_db
    User = FabUser
    Database = CoreDatabase
    SqlaTable = Dataset
    Slice = Chart
    Dashboard = Dash


def _get_admin() -> User:
    return db.session.query(User).filter_by(username="admin").one()


def _engine_connect(database: Database):
    get_engine = getattr(database, "get_sqla_engine", None)
    if get_engine is None:
        return database.get_sqla_engine_with_context()
    return get_engine()


def _wait_for_oracle(database, attempts: int = 40) -> None:
    from sqlalchemy import text

    last: Exception | None = None
    for _ in range(attempts):
        try:
            engine_ctx = _engine_connect(database)
            if hasattr(engine_ctx, "__enter__"):
                with engine_ctx as engine:
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1 FROM dual"))
            else:
                with engine_ctx.connect() as conn:
                    conn.execute(text("SELECT 1 FROM dual"))
            return
        except Exception as exc:  # noqa: BLE001 — retry until Oracle accepts thin connections
            last = exc
            time.sleep(3)
    raise RuntimeError(f"Oracle was not reachable from Superset: {last}")


def _upsert_database(admin: User) -> Database:
    password = os.environ.get("APP_USER_PASSWORD") or "OracleDemo1"
    uri = URI_TEMPLATE.format(password=password)
    database = db.session.query(Database).filter_by(database_name=DATABASE_NAME).one_or_none()
    if database is None:
        database = Database(database_name=DATABASE_NAME, expose_in_sqllab=True)
        database.created_by = admin
        database.changed_by = admin
        db.session.add(database)
    database.set_sqlalchemy_uri(uri)
    db.session.flush()
    _wait_for_oracle(database)
    return database


def _upsert_dataset(admin: User, database: Database, yaml_stem: str) -> SqlaTable:
    path = DATASET_DIR / f"{yaml_stem}.yaml"
    sql = dataset_sql(path)
    table_name = dataset_name(path)
    table = (
        db.session.query(SqlaTable)
        .filter_by(table_name=table_name, database_id=database.id)
        .one_or_none()
    )
    if table is None:
        table = SqlaTable(
            table_name=table_name,
            database_id=database.id,
            sql=sql,
            is_sqllab_view=True,
        )
        table.owners = [admin]
        table.created_by = admin
        table.changed_by = admin
        db.session.add(table)
        db.session.flush()
    else:
        table.sql = sql
    table.fetch_metadata()
    for col in table.columns:
        if str(col.column_name).upper() == "USAGE_DATE":
            col.is_dttm = True
            col.type = "DATE"
            col.python_date_format = "smart_date"
    db.session.flush()
    return table


def _metric(column: str) -> dict:
    return {
        "aggregate": "SUM",
        "column": {"column_name": column, "type": "NUMERIC"},
        "expressionType": "SIMPLE",
        "hasCustomLabel": False,
        "label": f"SUM({column})",
        "optionName": f"metric_{column}",
    }


def _with_datasource(table, payload: dict) -> str:
    payload["datasource"] = f"{table.id}__table"
    return json.dumps(payload)


def _category_bar_params(table, metric_column: str, x_axis: str) -> str:
    """Categorical bar: nvd3 Distribution Bar is not registered in Superset 6.1."""
    return _with_datasource(
        table,
        {
            "viz_type": "echarts_timeseries_bar",
            "x_axis": x_axis,
            "metrics": [_metric(metric_column)],
            "groupby": [],
            "row_limit": 40,
            "color_scheme": "supersetColors",
            "show_legend": False,
            "y_axis_format": ",.2f",
            "adhoc_filters": [],
            "order_desc": True,
            "orientation": "horizontal",
            "rich_tooltip": True,
            "x_axis_sort_asc": False,
            "x_axis_sort_series": "sum",
            "x_axis_sort_series_ascending": False,
        },
    )


def _timeseries_params(table, metric_column: str, series: list[str]) -> str:
    return _with_datasource(
        table,
        {
            "viz_type": "echarts_timeseries_bar",
            "x_axis": "USAGE_DATE",
            "granularity_sqla": "USAGE_DATE",
            "time_grain_sqla": "P1D",
            "metrics": [_metric(metric_column)],
            "groupby": series,
            "row_limit": 10000,
            "adhoc_filters": [],
            "color_scheme": "supersetColors",
            "show_legend": True,
            "rich_tooltip": True,
            "y_axis_format": ",.2f",
        },
    )


def _big_number_params(table, metric_column: str, subheader: str) -> str:
    return _with_datasource(
        table,
        {
            "viz_type": "big_number_total",
            "metric": _metric(metric_column),
            "subheader": subheader,
            "y_axis_format": ",.2f",
            "header_font_size": 0.4,
            "subheader_font_size": 0.15,
        },
    )


def _watermark_params(table) -> str:
    return _with_datasource(
        table,
        {
            "viz_type": "table",
            "query_mode": "raw",
            "all_columns": [
                "JOB_NAME",
                "LAST_SUCCESS_END",
                "LAST_SUCCESS_RUN_ID",
                "UPDATED_AT",
            ],
            "percent_metrics": [],
            "metrics": [],
            "order_by_cols": [],
            "row_limit": 10,
            "server_page_length": 10,
            "align_pn": False,
            "color_pn": False,
            "show_cell_bars": False,
        },
    )


def _query_context_for(table, viz_type: str, params: dict) -> str:
    if viz_type == "table":
        queries = [
            {
                "columns": params.get("all_columns") or [],
                "metrics": [],
                "row_limit": params.get("row_limit") or 10,
                "extras": {},
                "is_timeseries": False,
            }
        ]
    elif viz_type == "echarts_timeseries_bar":
        x_axis = params.get("x_axis") or "USAGE_DATE"
        metrics = params.get("metrics") or []
        if x_axis == "USAGE_DATE":
            queries = [
                {
                    "granularity": "USAGE_DATE",
                    "metrics": metrics,
                    "columns": params.get("groupby") or [],
                    "is_timeseries": True,
                    "extras": {"time_grain_sqla": params.get("time_grain_sqla") or "P1D"},
                    "row_limit": params.get("row_limit") or 10000,
                }
            ]
        else:
            orderby = [[metrics[0], False]] if metrics else []
            queries = [
                {
                    "metrics": metrics,
                    "columns": [x_axis],
                    "is_timeseries": False,
                    "orderby": orderby,
                    "extras": {},
                    "row_limit": params.get("row_limit") or 40,
                }
            ]
    elif viz_type == "big_number_total":
        queries = [
            {
                "metrics": [params["metric"]],
                "is_timeseries": False,
                "extras": {},
                "row_limit": 1,
            }
        ]
    else:
        queries = [
            {
                "metrics": params.get("metrics") or [],
                "groupby": params.get("groupby") or [],
                "is_timeseries": False,
                "extras": {},
                "row_limit": params.get("row_limit") or 10000,
            }
        ]
    return json.dumps(
        {
            "datasource": {"id": table.id, "type": "table"},
            "force": False,
            "queries": queries,
            "form_data": params,
            "result_format": "json",
            "result_type": "full",
        }
    )


def _upsert_chart(admin, table, name: str, viz_type: str, params: str):
    chart = db.session.query(Slice).filter_by(slice_name=name).one_or_none()
    if chart is None:
        chart = Slice(slice_name=name)
        chart.owners = [admin]
        chart.created_by = admin
        db.session.add(chart)
    chart.datasource_id = table.id
    chart.datasource_type = "table"
    chart.datasource_name = table.table_name
    chart.viz_type = viz_type
    chart.params = params
    chart.query_context = _query_context_for(table, viz_type, json.loads(params))
    chart.changed_by = admin
    db.session.flush()
    return chart


def _chart_node(chart: Slice, row_id: str, width: int, height: int) -> tuple[str, dict]:
    node_id = f"CHART-{chart.id}"
    uuid_value = getattr(chart, "uuid", None)
    return node_id, {
        "type": "CHART",
        "id": node_id,
        "children": [],
        "parents": ["ROOT_ID", "GRID_ID", row_id],
        "meta": {
            "chartId": chart.id,
            "width": width,
            "height": height,
            "sliceName": chart.slice_name,
            "uuid": str(uuid_value) if uuid_value else str(chart.id),
        },
    }


def _row_node(row_id: str, children: list[str]) -> dict:
    return {
        "type": "ROW",
        "id": row_id,
        "children": children,
        "parents": ["ROOT_ID", "GRID_ID"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"},
    }


def _upsert_dashboard(admin: User, layout_rows: list[list[tuple[Slice, int, int]]]) -> Dashboard:
    dashboard = db.session.query(Dashboard).filter_by(slug=DASHBOARD_SLUG).one_or_none()
    if dashboard is None:
        dashboard = Dashboard(dashboard_title="OCP cost warehouse (BRL)", slug=DASHBOARD_SLUG)
        dashboard.owners = [admin]
        dashboard.created_by = admin
        db.session.add(dashboard)
        db.session.flush()
    position: dict = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "children": [],
            "parents": ["ROOT_ID"],
        },
        "HEADER_ID": {
            "type": "HEADER",
            "id": "HEADER_ID",
            "meta": {"text": "OCP cost warehouse (BRL)"},
        },
    }
    grid_children: list[str] = []
    charts: list[Slice] = []
    for index, row in enumerate(layout_rows):
        row_id = f"ROW-{index}"
        child_ids: list[str] = []
        for chart, width, height in row:
            charts.append(chart)
            chart_id, chart_node = _chart_node(chart, row_id, width=width, height=height)
            position[chart_id] = chart_node
            child_ids.append(chart_id)
        position[row_id] = _row_node(row_id, child_ids)
        grid_children.append(row_id)
    position["GRID_ID"]["children"] = grid_children
    dashboard.position_json = json.dumps(position)
    dashboard.published = True
    dashboard.changed_by = admin
    dashboard.slices = charts
    dashboard.json_metadata = json.dumps(
        {
            "timed_refresh_immune_slices": [],
            "expanded_slices": {},
            "refresh_frequency": 0,
            "color_scheme": "supersetColors",
            "label_colors": {},
        }
    )
    db.session.flush()
    return dashboard


def seed() -> None:
    from superset.app import create_app

    app = create_app()
    _load_superset_models()
    with app.app_context():
        admin = _get_admin()
        database = _upsert_database(admin)
        datasets = {stem: _upsert_dataset(admin, database, stem) for stem in DATASET_FILES}
        supplementary = datasets["supplementary"]
        infra = datasets["infra"]
        cost_total = datasets["cost_total"]
        watermark = datasets["watermark"]
        total_chart = _upsert_chart(
            admin,
            supplementary,
            "Supplementary total (BRL)",
            "big_number_total",
            _big_number_params(supplementary, "SUPPLEMENTARY_TOTAL", "priced supplementary layer"),
        )
        watermark_chart = _upsert_chart(
            admin,
            watermark,
            "ETL watermark freshness",
            "table",
            _watermark_params(watermark),
        )
        by_project = _upsert_chart(
            admin,
            supplementary,
            "Supplementary by project (BRL)",
            "echarts_timeseries_bar",
            _category_bar_params(supplementary, "SUPPLEMENTARY_TOTAL", "PROJECT"),
        )
        by_day = _upsert_chart(
            admin,
            supplementary,
            "Supplementary by day (BRL)",
            "echarts_timeseries_bar",
            _timeseries_params(supplementary, "SUPPLEMENTARY_TOTAL", []),
        )
        infra_chart = _upsert_chart(
            admin,
            infra,
            "Infrastructure by project (BRL, 0.0 expected)",
            "echarts_timeseries_bar",
            _category_bar_params(infra, "INFRA_TOTAL", "PROJECT"),
        )
        cost_total_chart = _upsert_chart(
            admin,
            cost_total,
            "Cost total by project (BRL)",
            "echarts_timeseries_bar",
            _category_bar_params(cost_total, "COST_TOTAL", "PROJECT"),
        )
        dashboard = _upsert_dashboard(
            admin,
            [
                [(total_chart, 4, 32), (watermark_chart, 8, 32)],
                [(by_project, 12, 50)],
                [(by_day, 12, 50)],
                [(infra_chart, 6, 50), (cost_total_chart, 6, 50)],
            ],
        )
        db.session.commit()
        print(f"seeded dashboard id={dashboard.id} slug={dashboard.slug}")


if __name__ == "__main__":
    seed()
