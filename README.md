# Cost Management historical ETL

Copy Hybrid Cloud Console OpenShift project cost reports into a **lab Oracle** warehouse. Stored rows are extract-time snapshots. Currency is the API `units` value (this org: BRL), not hardcoded USD.

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

## Lab rollback

Stop the container and drop the `oracle-data` volume. SaaS Cost Management is **unchanged**.

```bash
podman-compose down -v
# equivalent: podman compose -f compose.yaml down -v
```

That removes local Oracle data only. Hybrid Cloud Console history and credentials are not modified.

## Daily job

Overlap plus the **current calendar month**. On day 2, also re-pull the **previous month**. Month-bounded `start_date`/`end_date` only — never `filter[time_scope_value]=-90`.
