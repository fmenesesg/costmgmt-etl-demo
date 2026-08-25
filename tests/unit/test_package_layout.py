"""Structural checks for the ETL package layout (task 1.1)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_declares_runtime_and_test_dependencies() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "cost-mgmt-etl"' in pyproject
    # PyPI install name is oracledb; design driver name is python-oracledb.
    assert "python-oracledb" in pyproject
    for package in ("oracledb", "httpx", "pytest"):
        assert package in pyproject, f"{package} must be declared in pyproject.toml"


def test_package_init_module_exists() -> None:
    init_path = REPO_ROOT / "cost_mgmt_etl" / "__init__.py"
    assert init_path.is_file()
    source = init_path.read_text(encoding="utf-8")
    assert "Cost Management historical ETL" in source
