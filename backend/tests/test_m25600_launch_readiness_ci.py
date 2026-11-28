"""M25600 — Master-only readiness; configuration syntax is never deployment proof."""
import pytest

from app.launch_readiness import REQUIREMENTS, readiness_manifest


def test_every_launch_requirement_explicitly_assigned_and_not_auto_enabled():
    report = readiness_manifest({})
    assert report["scope"] == "AI_STUDIO_MASTER_RELEASE_READINESS"
    assert report["mode"] == "READ_ONLY_NO_ACTIVATION"
    assert report["status"] == "BLOCKED"
    assert report["total_gates"] == len(REQUIREMENTS)
    assert report["total_gates"] >= 18
    assert report["unverified_gates"] == len(REQUIREMENTS)
    assert len({item["id"] for item in report["requirements"]}) == len(REQUIREMENTS)
    assert {item["category"] for item in report["requirements"]} == {
        "identidade", "cadastro", "infra", "pagamentos",
    }
    for item in report["requirements"]:
        assert item["status"] == "INTEGRATION_AND_ATTESTATION_REQUIRED"
        assert item["production_verified"] is False
        assert len(item["required_evidence"]) >= 15
        assert isinstance(item["engineering_source_present"], bool)
    for key in (
        "real_invites_active","password_reset_active","real_pix_active",
        "financial_closing_authorized","writes_performed","config_valid_is_live_proof"
    ):
        assert report[key] is False


def syntax_only_config():
    common = "postgresql://{role}:{password}@database.frfinance.com.br:5432/frfinance_prod?sslmode=verify-full"
    return {
        "APP_URL": "https://app.frfinance.com.br",
        "ENVIRONMENT": "production",
        "FR_FINANCE_AUTH_PRODUCTION_GATE": "OCI_STAGING_REVIEWED",
        "AUTH_SECRET": "f" * 48,
        "AUTH_RATE_LIMIT_HMAC_KEY": "g" * 48,
        "AUTH_DATABASE_URL": common.format(role="frc_ai_auth",password="a"*20),
        "AUTH_VERIFIER_DATABASE_URL": common.format(role="frc_ai_verifier",password="b"*20),
        "DATABASE_URL": common.format(role="frc_ai_app",password="c"*20),
        "SMTP_HOST": "smtp.frfinance.com.br",
        "SMTP_PORT": "587",
        "SMTP_USER": "sender@frfinance.com.br",
        "SMTP_PASSWORD": "not-a-real-password-example",
        "FR_FINANCE_EMAIL_FROM": "comunicados@frfinance.com.br",
    }


def test_valid_syntax_still_never_auto_approves_a_single_gate():
    env = syntax_only_config()
    report = readiness_manifest(env)
    assert report["smtp_config_syntax_valid"] is True
    assert report["production_auth_config_syntax_valid"] is True
    assert report["public_https_origin_syntax_valid"] is True
    assert report["status"] == "BLOCKED"
    assert report["unverified_gates"] == len(REQUIREMENTS)
    assert all(not gate["production_verified"] for gate in report["requirements"])
    output = str(report)
    for secret in (
        env["AUTH_SECRET"], env["SMTP_PASSWORD"],
        env["AUTH_DATABASE_URL"], env["AUTH_VERIFIER_DATABASE_URL"],
        env["DATABASE_URL"], env["AUTH_RATE_LIMIT_HMAC_KEY"],
    ):
        assert secret not in output


@pytest.mark.parametrize("changed", [
    {"APP_URL": "http://app.frfinance.com.br"},
    {"SMTP_PORT": "25"},
    {"FR_FINANCE_EMAIL_FROM": ""},
    {"FR_FINANCE_AUTH_PRODUCTION_GATE": "UNVERIFIED"},
    {"ENVIRONMENT": "development"},
])
def test_unsafe_or_incomplete_config_cannot_mark_readiness_valid(changed):
    env = syntax_only_config()
    env.update(changed)
    report = readiness_manifest(env)
    assert report["status"] == "BLOCKED"
    assert not (report["smtp_config_syntax_valid"] and
                report["production_auth_config_syntax_valid"] and
                report["public_https_origin_syntax_valid"])
    assert report["real_pix_active"] is False


def test_api_route_is_master_only_and_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    code = (root / "backend/app/routers/master.py").read_text()
    service = (root / "backend/app/launch_readiness.py").read_text()
    assert '@router.get("/launch-readiness")' in code
    assert "session: AuthenticatedSession = Depends(require_master)" in code
    assert "platform_release_manifest(os.environ)" in code
    for forbidden in ("INSERT INTO ", "UPDATE public.", "DELETE FROM public.", "asyncpg.connect("):
        assert forbidden not in service
    assert "os.environ" not in service
