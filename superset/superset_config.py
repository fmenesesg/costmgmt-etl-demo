"""Superset 6.1.0 lab config: sqlite metadata and python-oracledb thin."""

import os
import sys

import oracledb
from sqlalchemy.dialects import registry

oracledb.version = "8.3.0"
sys.modules["cx_Oracle"] = oracledb
registry.register(
    "oracle.oracledb",
    "sqlalchemy.dialects.oracle.cx_oracle",
    "OracleDialect_cx_oracle",
)

SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
TALISMAN_ENABLED = False
