"""Working-tree secret scan (task 1.5). No git repository is required."""

from pathlib import Path

from tests.unit.git_secret_scan import find_secret_findings

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_working_tree_has_no_hcc_or_production_oracle_secrets() -> None:
    findings = find_secret_findings(REPO_ROOT)
    assert findings == [], findings


def test_scanner_flags_hcc_client_secret_literal(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text(
        "COSTMGMT_CLIENT_ID=service-account-id-123\n"
        "COSTMGMT_CLIENT_SECRET=hcc-live-secret-value-99\n",
        encoding="utf-8",
    )
    findings = find_secret_findings(tmp_path)
    joined = "\n".join(findings)
    assert "COSTMGMT_CLIENT_SECRET" in joined
    assert "hcc-live-secret-value-99" in joined or "CLIENT_SECRET" in joined


def test_scanner_skips_gitignored_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "COSTMGMT_CLIENT_ID=service-account-id-123\n"
        "COSTMGMT_CLIENT_SECRET=hcc-live-secret-value-99\n",
        encoding="utf-8",
    )
    assert find_secret_findings(tmp_path) == []


def test_scanner_allows_oracledemo1_placeholder_and_flags_prod_like_password(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env.example").write_text(
        "COSTMGMT_CLIENT_ID=\nCOSTMGMT_CLIENT_SECRET=\nORACLE_PASSWORD=OracleDemo1\n",
        encoding="utf-8",
    )
    allowed = find_secret_findings(tmp_path)
    assert allowed == [], allowed

    (tmp_path / "notes.env").write_text(
        "ORACLE_PASSWORD=P@ssw0rd-ProdVault-2026\n",
        encoding="utf-8",
    )
    flagged = find_secret_findings(tmp_path)
    joined = "\n".join(flagged)
    assert "ORACLE_PASSWORD" in joined
    assert "P@ssw0rd-ProdVault-2026" in joined or "production-looking" in joined.lower()
