"""M37469 — canonical offline operational release blockers; never grant real authority."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.saas_operational_blockers_m37469 import (
    CI_MILESTONES, KNOWN_RUNTIME_FLAGS, NEXT_OPERATOR_PROOFS,
    PROVIDER_GATES, PRIORITY_ORDER, READ_ONLY_STATE,
    REAL_ACTIONS, REQUIRED_LIVE_DOMAINS,
    _check_ci_sources, build_operational_blocker_report,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/aistudio_m37469_release_blockers_readonly.py"


def report(*,root=ROOT,env=None):
    return build_operational_blocker_report(root=root,env=env)


def test_existing_repo_presents_all_twelve_test_files_for_eleven_packages():
    data=report()
    assert data["ci_package_count"]==11
    assert data["ci_source_packages_present"]==11
    assert len(CI_MILESTONES)==11
    assert sum(len(paths) for _,paths in CI_MILESTONES)==12
    assert [x["id"] for x in data["ci_package_sources"]]==[
        f"M374{p}" for p in range(58,69)
    ]
    assert all(x["source_files_present"] for x in data["ci_package_sources"])
    assert all(not x["real_staging_verified"] for x in data["ci_package_sources"])
    assert all(
        len(digest)==64 and all(c in "0123456789abcdef" for c in digest)
        for x in data["ci_package_sources"]
        for digest in x["sha256_of_code_only_not_ci_proof"]
    )


def test_20_canonical_existing_release_gates_stay_unverified():
    data=report()
    assert data["live_gate_count"]==20
    assert data["live_gates_verified"]==0
    assert data["live_gates_unverified"]==20
    assert len(data["blockers"])==20
    assert {x["gate_id"] for x in data["blockers"]}==set(PRIORITY_ORDER)
    assert all(x["verified_live"] is False for x in data["blockers"])
    assert all(x["status"]=="EXTERNAL_STAGING_PROOF_REQUIRED" for x in data["blockers"])
    assert all(x["required_evidence"] and x["acceptance_proof"]
               for x in data["blockers"])
    assert data["provider_gate_count"]==len(PROVIDER_GATES)==7
    assert data["provider_gates_verified"]==0


def test_source_coverage_never_promotes_production_rights():
    data=report()
    assert data["release_status"]=="BLOCKED_REQUIRES_INDEPENDENT_LIVE_PROOFS"
    assert data["production_authorized"] is False
    assert data["staging_deployment_authorized"] is False
    assert data["release_approval_decision"]=="NOT_ISSUED"
    assert data["ci_proof_is_live_attestation"] is False
    assert data["ci_test_run_passed_by_this_report"] is False
    assert data["ci_only_code_cannot_activate_users"] is True
    assert data["writes_performed"] is False
    assert data["network_calls_performed"] is False
    assert data["sql_migrations_applied"] is False
    assert data["financial_tables_written"] is False
    assert all(value is False
               for value in data["all_live_actions_disabled_by_this_tool"].values())


def test_no_secret_values_or_provider_claims_leaked():
    marker="definitely-secret-never-print-04920"
    data=report(env={
        "AUTH_DATABASE_URL":"postgres://"+marker,
        "AUTH_SECRET":marker,
        "MP_CLIENT_SECRET":marker,
        "SMTP_PASSWORD":marker,
        "OCI_API_KEY":marker,
        "FR_FINANCE_PIX_REAL":marker,
    })
    encoded=json.dumps(data,ensure_ascii=False)
    assert marker not in encoded
    for k in ("AUTH_SECRET","MP_CLIENT_SECRET","SMTP_PASSWORD","OCI_API_KEY"):
        assert k not in encoded
    assert data["runtime_flag_classifications_only"]["FR_FINANCE_PIX_REAL"]=="NON_OFF_DO_NOT_DEPLOY"
    assert data["psp_provider_state"]=="NOT_QUERIED_UNVERIFIED"
    assert data["oci_staging_vm_running"]=="NOT_QUERIED_UNVERIFIED"
    assert data["email_provider_state"]=="NOT_QUERIED_UNVERIFIED"


@pytest.mark.parametrize("flag",KNOWN_RUNTIME_FLAGS)
def test_only_exact_OFF_can_be_classified_declared_off(flag):
    observed=report(env={flag:"OFF"})["runtime_flag_classifications_only"]
    assert observed[flag]=="DECLARED_OFF"
    assert all(
        observed[other]=="NOT_DECLARED"
        for other in KNOWN_RUNTIME_FLAGS if other!=flag
    )
    assert report(env={flag:"ON"})["runtime_flag_classifications_only"][flag]=="NON_OFF_DO_NOT_DEPLOY"
    assert report(env={flag:"off"})["runtime_flag_classifications_only"][flag]=="NON_OFF_DO_NOT_DEPLOY"
    assert report(env={flag:"DESATIVADO"})["runtime_flag_classifications_only"][flag]=="NON_OFF_DO_NOT_DEPLOY"
    assert report(env={flag:"TRUE"})["runtime_flag_classifications_only"][flag]=="NON_OFF_DO_NOT_DEPLOY"
    assert report(env={flag:""})["runtime_flag_classifications_only"][flag]=="NON_OFF_DO_NOT_DEPLOY"


@pytest.mark.parametrize("evidence",[
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FR_FINANCE_LICENSE_REAL":"ON"},
    {"FR_FINANCE_PAYMENT_REAL":"ON"},
    {"FR_FINANCE_ACTIVATION_REAL":"ON"},
    {
        "FR_FINANCE_SAAS_REAL":"OFF",
        "FR_FINANCE_PIX_REAL":"OFF",
        "FR_FINANCE_LICENSE_REAL":"OFF",
        "FR_FINANCE_PAYMENT_REAL":"OFF",
        "FR_FINANCE_ACTIVATION_REAL":"OFF",
        "ENVIRONMENT":"production",
        "APP_URL":"https://frfinance.com.br",
    },
])
def test_even_all_off_or_prod_env_cannot_unblock_without_live_proof(evidence):
    data=report(env=evidence)
    assert not data["production_authorized"]
    assert not data["staging_deployment_authorized"]
    assert data["live_gates_verified"]==0


def test_required_live_domains_partition_all_canonical_gates():
    all_keys=[gate for ids in REQUIRED_LIVE_DOMAINS.values() for gate in ids]
    assert len(all_keys)==20
    assert len(all_keys)==len(set(all_keys))
    assert set(all_keys)==set(PRIORITY_ORDER)
    assert set(REQUIRED_LIVE_DOMAINS)=={
        "IDENTITY_REAL_E2E","CONTRACT_LEGAL_ACCEPTANCE",
        "OCI_AND_PRODUCTION_RUNTIME","SMTP_DELIVERY","PAYMENTS_AND_LICENSE",
    }


def test_action_queue_names_real_world_evidence_instead_of_ci_repeats():
    items=report()["priority_external_proofs"]
    assert len(items)==9
    assert [p["id"] for p in items]==[p[0] for p in NEXT_OPERATOR_PROOFS]
    assert len({x["id"] for x in items})==len(items)
    assert all(x["gate_id"] in PRIORITY_ORDER for x in items)
    assert all(x["state"]=="REAL_WORLD_EVIDENCE_NOT_COLLECTED_BY_THIS_REPORT"
               for x in items)
    assert len(REAL_ACTIONS)==7
    assert len(READ_ONLY_STATE)==10
    assert not any(READ_ONLY_STATE.values())


def test_missing_sources_do_not_change_live_release_blockers(tmp_path):
    data=report(root=tmp_path)
    assert data["ci_package_count"]==11
    assert data["ci_source_packages_present"]==0
    assert all(not x["source_files_present"] for x in data["ci_package_sources"])
    assert data["live_gates_verified"]==0
    assert data["production_authorized"] is False


def test_partial_sources_never_attest_complete_milestone(tmp_path):
    path=tmp_path/"backend/tests/test_m37459_saas_api_contract_ci.py"
    path.parent.mkdir(parents=True)
    path.write_text("# one of two files\n")
    data=report(root=tmp_path)
    assert data["ci_source_packages_present"]==0
    x=next(x for x in data["ci_package_sources"] if x["id"]=="M37459")
    assert x["sha256_of_code_only_not_ci_proof"]==[]
    assert x["real_staging_verified"] is False


def test_symlink_source_outside_repo_not_accepted(tmp_path):
    source=tmp_path/"outside.py"
    source.write_text("# unrelated source\n")
    expected=tmp_path/"backend/tests/test_m37458_saas_consent_before_preparation_ci.py"
    expected.parent.mkdir(parents=True)
    expected.symlink_to(source)
    data=report(root=tmp_path)
    assert data["ci_source_packages_present"]==0
    assert data["ci_package_sources"][0]["source_files_present"] is False


def test_large_source_file_does_not_spoof_ci_package(tmp_path):
    expected=tmp_path/"backend/tests/test_m37458_saas_consent_before_preparation_ci.py"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"x"*2_000_001)
    data=report(root=tmp_path)
    assert data["ci_package_sources"][0]["source_files_present"] is False


@pytest.mark.parametrize("bad_root",[None,"/mnt/data",False,123,{}])
def test_untrusted_root_type_denied(bad_root):
    with pytest.raises(ValueError):
        report(root=bad_root)


@pytest.mark.parametrize("bad_env",[False,123,"OTHER",[]])
def test_untrusted_environment_type_denied(bad_env):
    with pytest.raises(ValueError):
        report(env=bad_env)


def load_script():
    spec=importlib.util.spec_from_file_location("m37469_cli",SCRIPT)
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_audit_has_no_network_or_db_reads(capsys):
    cli=load_script()
    assert cli.main(["audit"])==0
    printed=capsys.readouterr().out
    assert "M37469_READONLY_REPORT=PASS" in printed
    assert "CI_SOURCE_PACKAGES=11/11" in printed
    assert "LIVE_PROOFS_VERIFIED=0/20" in printed
    assert "PROVIDER_GATES_VERIFIED=0/7" in printed
    assert "REAL_ACTIVATION_AUTHORIZED=NO" in printed
    assert "PRODUCTION_RELEASE=BLOCKED" in printed
    assert "NETWORK_AND_DATABASE_IO=NONE" in printed
    assert "MIGRATIONS_LOCAL_OR_STAGING=NOT_EXECUTED" in printed


def test_cli_plan_is_actionable_but_has_no_activation(capsys):
    cli=load_script()
    assert cli.main(["plan"])==0
    out=capsys.readouterr().out
    assert out.count("PRIORIDADE_OPERACIONAL=")==9
    assert out.count("LIVE_GATE_UNVERIFIED=")==20
    assert "OCI_STAGING_RUNNING_INSTANCE" in out
    assert "PUBLISHED_CONTRACT_LEGAL_CONSENT" in out
    assert "PIX_OUTBOUND_COMMERCIALLY_APPROVED" in out
    assert "PRODUCTION_RELEASE=BLOCKED" in out


def test_cli_json_is_valid_with_all_false_authorizations(capsys):
    cli=load_script()
    assert cli.main(["json"])==0
    data=json.loads(capsys.readouterr().out)
    assert data["package"]=="M37469"
    assert data["mode"]=="LOCAL_READ_ONLY_NO_NETWORK_NO_DB"
    assert data["production_authorized"] is False
    assert data["staging_deployment_authorized"] is False
    assert len(data["blockers"])==20


def test_existing_workflow_will_run_m37469_but_never_runner_in_staging_chain():
    yml=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()
    assert "backend/tests/test_m37469_release_blockers_readonly.py" in yml
    assert "aistudio_m37469_release_blockers_readonly.py plan" in yml
    chain=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "aistudio_m37469_release_blockers_readonly.py" not in chain
    assert "M37469" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()


def test_cli_contains_no_operational_side_effects():
    content=SCRIPT.read_text()
    assert "os.environ" in content
    assert "build_operational_blocker_report" in content
    for forbidden in (
        "oci compute instance launch", "subprocess.run(",
        "asyncpg.connect(", "psycopg.connect(", "requests.get(",
        "httpx.get(", "INSERT INTO ", "UPDATE public.",
        "os.environ[", "send_mail(", "create_user(", "authorize(",
    ):
        assert forbidden not in content


def test_hash_changes_when_source_changes_without_ever_promoting_status(tmp_path):
    name="backend/tests/test_m37458_saas_consent_before_preparation_ci.py"
    p=tmp_path/name
    p.parent.mkdir(parents=True)
    p.write_text("one\n")
    first=report(root=tmp_path)
    p.write_text("two\n")
    second=report(root=tmp_path)
    assert first["ci_package_sources"][0]["sha256_of_code_only_not_ci_proof"] != second["ci_package_sources"][0]["sha256_of_code_only_not_ci_proof"]
    assert first["production_authorized"] is False
    assert second["production_authorized"] is False
