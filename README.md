# Cost Management historical ETL

Copy Hybrid Cloud Console OpenShift project cost reports into a **lab Oracle** warehouse so cost history survives beyond the SaaS **~90-day** retention window. Stored rows are extract-time snapshots. Currency is the API `units` value (this org: BRL), not hardcoded USD.

**Architecture, integration diagrams, and incremental ingestion:** [docs/architecture.md](docs/architecture.md)

## Compose engine

This host uses **podman**, not docker. First engine: `podman compose` / `podman-compose`. `compose.yaml` stays compatible with Docker Compose v2.

Lab image tag: `docker.io/gvenzl/oracle-free:23.26.2-slim` (digest pin optional).

## Lab start

```bash
cp .env.example .env   # set COSTMGMT_CLIENT_ID / COSTMGMT_CLIENT_SECRET locally; never commit .env
podman-compose up -d oracle
# Lab DSN: localhost:1521/FREEPDB1  user costmgmt  password OracleDemo1 (overridable via env)
```

`python -m cost_mgmt_etl.stack compose.yaml` starts only that known compose file. `requirements.txt` is a pip pin file, not a stack executable.

## Open-source BI (Apache Superset)

Profile `bi` starts one extra Superset container on the lab Oracle network. Default `podman-compose up -d oracle` and `python -m cost_mgmt_etl.stack compose.yaml` do **not** start BI.

```bash
cp .env.example .env   # set SUPERSET_SECRET_KEY locally if you override the lab placeholder
podman-compose --profile bi up -d
# UI: http://127.0.0.1:8088  (sqlite metadata on volume superset-home)
```

Warehouse Test Connection URI (python-oracledb thin, lab `FREEPDB1` only):

```
oracle+oracledb://costmgmt:${APP_USER_PASSWORD}@oracle:1521/?service_name=FREEPDB1
```

Use `APP_USER_PASSWORD` from `.env`. Do not put `COSTMGMT_CLIENT_*` on the BI container.

Class A charts query `FACT_OCP_COST_BY_PROJECT` in **BRL** only (remaining grain `GROUP BY`). Supplementary and infra are separate series; never add `cost_total` to those layers. Do **not** mix Grafana Infinity or HCC Cost Explorer API series with warehouse measures.

SQL for the four datasets lives in `superset/datasets/`. Dashboard slug: `ocp-cost-warehouse`.

## Lab rollback

Stop the container and drop the `oracle-data` volume. SaaS Cost Management is **unchanged**.

```bash
podman-compose down -v
# equivalent: podman compose -f compose.yaml down -v
```

That removes local Oracle data only. Hybrid Cloud Console history and credentials are not modified.

Stop only BI and keep warehouse facts: `podman-compose --profile bi down` **without** `-v` (does not drop `oracle-data`). You may remove volume `superset-home` afterwards if you want a clean sqlite metadata store. `podman-compose down -v` still wipes Oracle.

## Daily job

Re-pull the **current calendar month** every run. On **day 2**, also re-pull the **previous month**. Month-bounded `start_date`/`end_date` only — never `filter[time_scope_value]=-90`. Full policy and diagrams: [docs/architecture.md](docs/architecture.md) ([Incremental ingestion](docs/architecture.md#incremental-ingestion)).

```bash
# Load HCC credentials into gitignored .env first, then:
python -m cost_mgmt_etl run          # current month (and previous month on day 2)
python -m cost_mgmt_etl backfill     # last 4 billed months into lab Oracle
# Compose equivalent: podman-compose --profile etl up
```

After `backfill`, open the published dashboard (admin / admin):

```
http://127.0.0.1:8088/superset/dashboard/ocp-cost-warehouse/
```

The BI container seeds that dashboard on startup (`superset/bootstrap_dashboards.py`). Charts query warehouse SQL only (BRL).
