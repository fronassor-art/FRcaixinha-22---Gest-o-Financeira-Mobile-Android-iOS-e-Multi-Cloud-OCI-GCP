"""M37323-M37330: inert, read-only OCI bootstrap templates & contract tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys
from dataclasses import replace

import pytest

from app.oci_staging_bootstrap_plan import (
    BootstrapPlanBlocked,ROOT_RELATIVE,TEMPLATES,
    _CRITICAL_BLOCKERS,inspect_plan_only,
)

ROOT=Path(__file__).resolve().parents[2]


def fixture_repo(tmp_path):
    target=tmp_path/ROOT_RELATIVE
    target.mkdir(parents=True)
    source=ROOT/ROOT_RELATIVE
    for filename in TEMPLATES:
        shutil.copyfile(source/filename,target/filename)
    return tmp_path


def rewrite(root,filename,old,new):
    path=root/ROOT_RELATIVE/filename
    text=path.read_text()
    assert old in text
    path.write_text(text.replace(old,new))


def test_existing_deploy_templates_are_inert_and_secure():
    result=inspect_plan_only(ROOT)
    assert result.checked_templates==3
    assert len(result.content_sha256)==64
    assert result.files_read_only
    assert result.existing_vcn_reuse_only
    assert result.backend_loopback_only
    assert result.internet_https_requires_future_approval
    assert result.blocked_gates==_CRITICAL_BLOCKERS
    for flag in ("cloud_mutations","sql_applied","deployment_authorized",
                 "paid_resource_authorized","production_auth_authorized",
                 "user_activation_authorized","real_pix_authorized"):
        assert getattr(result,flag) is False


def test_checksum_deterministic_with_identical_repo_files(tmp_path):
    copied=fixture_repo(tmp_path)
    assert inspect_plan_only(ROOT).content_sha256==inspect_plan_only(copied).content_sha256


def test_missing_template_fails_closed(tmp_path):
    copied=fixture_repo(tmp_path)
    (copied/ROOT_RELATIVE/TEMPLATES[0]).unlink()
    with pytest.raises(BootstrapPlanBlocked,match="TEMPLATE_MISSING"):
        inspect_plan_only(copied)


def test_symlink_not_accepted(tmp_path):
    copied=fixture_repo(tmp_path)
    link=copied/ROOT_RELATIVE/TEMPLATES[0]
    link.unlink()
    link.symlink_to(ROOT/ROOT_RELATIVE/TEMPLATES[0])
    with pytest.raises(BootstrapPlanBlocked,match="SYMLINK"):
        inspect_plan_only(copied)


@pytest.mark.parametrize("filename,old,new",[
    (TEMPLATES[0],"--host 127.0.0.1","--host 0.0.0.0"),
    (TEMPLATES[0],"--port 8000","--port 5432"),
    (TEMPLATES[0],"--port 8000","--port 5433"),
    (TEMPLATES[1],"reverse_proxy 127.0.0.1:8000","reverse_proxy 0.0.0.0:8000"),
    (TEMPLATES[2],"ENVIRONMENT=homologation","ENVIRONMENT=production"),
    (TEMPLATES[2],"FRC_MP_ACCEPT_LIVE_NOTIFICATIONS=0","FRC_MP_ACCEPT_LIVE_NOTIFICATIONS=1"),
    (TEMPLATES[2],"FR_FINANCE_PIX_REAL=0","FR_FINANCE_PIX_REAL=1"),
    (TEMPLATES[2],"FRC_MP_OCI_STAGING_ENABLED=0","FRC_MP_OCI_STAGING_ENABLED=1"),
    (TEMPLATES[2],"FR_FINANCE_REAL_USER_ACTIVATION=0","FR_FINANCE_REAL_USER_ACTIVATION=1"),
    (TEMPLATES[2],"FR_FINANCE_REAL_MAIL=0","FR_FINANCE_REAL_MAIL=1"),
])
def test_unsafe_bind_or_activation_remains_blocked(tmp_path,filename,old,new):
    copied=fixture_repo(tmp_path)
    rewrite(copied,filename,old,new)
    with pytest.raises(BootstrapPlanBlocked):
        inspect_plan_only(copied)


@pytest.mark.parametrize("filename,required",[
    (TEMPLATES[0],"NoNewPrivileges=true"),
    (TEMPLATES[0],"ConditionPathExists=/etc/fr-finance/explicitly-reviewed-staging-deploy"),
    (TEMPLATES[0],"EnvironmentFile=/run/fr-finance/runtime.env"),
    (TEMPLATES[0],"ProtectSystem=strict"),
    (TEMPLATES[0],"ProtectHome=true"),
    (TEMPLATES[1],"Strict-Transport-Security"),
    (TEMPLATES[1],"handle /api/*"),
    (TEMPLATES[1],"respond 404"),
    (TEMPLATES[2],"ENVIRONMENT=homologation"),
])
def test_missing_safety_prerequisite_fails_closed(tmp_path,filename,required):
    copied=fixture_repo(tmp_path)
    rewrite(copied,filename,required,"UNSET")
    with pytest.raises(BootstrapPlanBlocked,match="SECURITY_REQUIREMENT_MISSING"):
        inspect_plan_only(copied)


def test_proxy_duplicate_backend_not_allowed(tmp_path):
    copied=fixture_repo(tmp_path)
    path=copied/ROOT_RELATIVE/TEMPLATES[1]
    path.write_text(path.read_text()+"\nreverse_proxy 127.0.0.1:8000\n")
    with pytest.raises(BootstrapPlanBlocked,match="PROXY_SCOPE_INVALID"):
        inspect_plan_only(copied)


def test_proxy_multiple_host_placeholders_not_allowed(tmp_path):
    copied=fixture_repo(tmp_path)
    path=copied/ROOT_RELATIVE/TEMPLATES[1]
    path.write_text(path.read_text()+"\n# {$FR_FINANCE_API_FQDN}\n")
    with pytest.raises(BootstrapPlanBlocked,match="HOST_PLACEHOLDER_INVALID"):
        inspect_plan_only(copied)


def test_duplicate_runtime_flag_not_allowed(tmp_path):
    copied=fixture_repo(tmp_path)
    path=copied/ROOT_RELATIVE/TEMPLATES[2]
    path.write_text(path.read_text()+"\nENVIRONMENT=homologation\n")
    with pytest.raises(BootstrapPlanBlocked,match="RUNTIME_FLAGS_NOT_DISABLED"):
        inspect_plan_only(copied)


def test_private_material_not_stored_in_templates():
    for filename in TEMPLATES:
        body=(ROOT/ROOT_RELATIVE/filename).read_text()
        for forbidden in (
            "BEGIN PRIVATE KEY","sk_live_","APP_SECRET=",
            "AUTH_SECRET=","DATABASE_URL=","postgresql://",
            "oci compute instance launch","terraform apply",
            "oci kms management vault create",
        ):
            assert forbidden not in body
    # The design is a proposal; it has no runnable Terraform or IAM changes.
    assert not list((ROOT/ROOT_RELATIVE).glob("*.tf"))


def test_plan_only_script_reports_no_deployment(capsys):
    path=ROOT/"backend/scripts/aistudio_oci_staging_bootstrap_plan_only.py"
    spec=importlib.util.spec_from_file_location("m37330_bootstrap",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main()==0
    output=capsys.readouterr().out
    assert "M37330_BOOTSTRAP=PLAN_ONLY_PASS" in output
    assert "M37330_TEMPLATES=3" in output
    assert "M37330_EXECUTABLE_DEPLOYMENT=NO" in output
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in output
    assert "PIX_REAL=OFF" in output
    assert "REAL_USER_ACTIVATION=OFF" in output


def test_source_is_offline_no_mutating_external_calls():
    paths=[
        ROOT/"backend/app/oci_staging_bootstrap_plan.py",
        ROOT/"backend/scripts/aistudio_oci_staging_bootstrap_plan_only.py",
    ]
    combined="\n".join(path.read_text() for path in paths)
    for operation in ("subprocess.","os.system(","requests.","httpx.",
                      "oci.core.","oci.key_management.",
                      "create_vault(","create_instance(","psycopg.connect(",
                      "asyncpg.connect("):
        assert operation not in combined
