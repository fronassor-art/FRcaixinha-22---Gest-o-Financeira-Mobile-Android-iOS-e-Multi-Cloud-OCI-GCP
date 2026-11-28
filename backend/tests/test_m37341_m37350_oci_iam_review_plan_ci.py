"""FR Finance M37341-M37350: no broad IAM, no real OCIDs in repo, offline CI."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import shutil

import pytest

from app.oci_iam_least_privilege_review import (
    IAMReviewBlocked, check_iam_template, TEMPLATE_PATH,
)
from app.oci_iam_readiness_readonly import _CANDIDATE_STATEMENT

ROOT = Path(__file__).resolve().parents[2]


def copy_template(tmp_path):
    source = ROOT / TEMPLATE_PATH
    destination = tmp_path / TEMPLATE_PATH
    destination.parent.mkdir(parents=True)
    shutil.copyfile(source, destination)
    return destination


def test_review_only_template_statically_valid():
    result = check_iam_template(ROOT)
    assert len(result.template_sha256) == 64
    assert result.expected_statements == 2
    assert result.read_only
    for attribute in (
        "identity_domain_unverified", "specific_instance_ocid_missing",
        "staging_compartment_id_not_versioned", "secret_ocid_missing",
        "effective_instance_principal_not_verified",
        "effective_secret_read_not_verified", "operator_approval_required",
    ):
        assert getattr(result, attribute) is True
    for attribute in (
        "policy_created", "dynamic_group_created", "vault_created",
        "cloud_changes", "deployment_authorized", "real_pix_authorized",
        "real_users_authorized",
    ):
        assert getattr(result, attribute) is False


def test_template_is_deterministic_with_copy(tmp_path):
    copy_template(tmp_path)
    assert check_iam_template(ROOT).template_sha256 == check_iam_template(tmp_path).template_sha256


def test_missing_file_fails_closed(tmp_path):
    (tmp_path / "infra/oci/staging-reuse").mkdir(parents=True)
    with pytest.raises(IAMReviewBlocked, match="TEMPLATE_MISSING"):
        check_iam_template(tmp_path)


def test_symlink_denied(tmp_path):
    destination = copy_template(tmp_path)
    destination.unlink()
    destination.symlink_to(ROOT / TEMPLATE_PATH)
    with pytest.raises(IAMReviewBlocked, match="TEMPLATE_MISSING"):
        check_iam_template(tmp_path)


@pytest.mark.parametrize("before,after", [
    ("instance.id = '__STAGING_INSTANCE_OCID__'", "instance.id != '__STAGING_INSTANCE_OCID__'"),
    ("all {instance.compartment.id", "any {instance.compartment.id"),
    ("instance.id = '__STAGING_INSTANCE_OCID__'", "instance.id = 'ocid1.instance.oc1..REAL'"),
    ("instance.id = '__STAGING_INSTANCE_OCID__'", "instance.id = '*'"),
    ("to read secret-bundles", "to manage secret-family"),
    ("to read secret-bundles", "to manage all-resources"),
    ("in compartment id __STAGING_COMPARTMENT_OCID__", "in tenancy"),
    ("where target.secret.id = '__APP_SECRET_OCID__'", ""),
    ("secret.id = '__APP_SECRET_OCID__'", "secret.id = '*'"),
    ("'__IDENTITY_DOMAIN__'", "'Default'"),
    ("OCI_RESOURCE_CREATION_AUTHORIZED=NO", "OCI_RESOURCE_CREATION_AUTHORIZED=YES"),
    ("PIX_REAL=OFF", "PIX_REAL=ON"),
    ("REAL_USER_ACTIVATION=OFF", "REAL_USER_ACTIVATION=ON"),
    ("INSTANCE_PRINCIPAL_TESTED=NO", "INSTANCE_PRINCIPAL_TESTED=YES"),
    ("EFFECTIVE_SECRET_READ_TESTED=NO", "EFFECTIVE_SECRET_READ_TESTED=YES"),
])
def test_broader_or_premature_iam_rights_denied(tmp_path, before, after):
    target = copy_template(tmp_path)
    body = target.read_text()
    assert before in body
    target.write_text(body.replace(before, after))
    with pytest.raises(IAMReviewBlocked):
        check_iam_template(tmp_path)


def test_duplicate_policy_line_denied(tmp_path):
    target = copy_template(tmp_path)
    with target.open("a") as out:
        out.write("\nPOLICY_NAME=fr-finance-staging-read-single-secret\n")
    with pytest.raises(IAMReviewBlocked, match="LEAST_PRIVILEGE_DENIED"):
        check_iam_template(tmp_path)


def test_secret_or_ocid_in_comment_also_denied(tmp_path):
    target = copy_template(tmp_path)
    with target.open("a") as out:
        out.write("\n# ocid1.instance.oc1..PRIVATE\n")
    with pytest.raises(IAMReviewBlocked, match="PRIVATE_DATA_DENIED"):
        check_iam_template(tmp_path)


@pytest.mark.parametrize("line", [
    "Allow dynamic-group fr-finance-staging-runtime to read secret-bundles in compartment fr-finance-staging",
    "Allow dynamic-group 'Default'/'fr-finance-staging-runtime' to read secret-bundles in compartment id ocid1.compartment.oc1..MOCK where target.secret.id = 'ocid1.vaultsecret.oc1..MOCK'",
    "Allow dynamic-group fr-finance-staging-runtime to read secret-bundles in tenancy where target.secret.id = 'ocid1.vaultsecret.oc1..MOCK'",
])
def test_iam_policy_candidate_supports_real_oracle_syntaxes(line):
    # A candidate does NOT mean authenticated permission or that secret exists.
    assert _CANDIDATE_STATEMENT.fullmatch(line)


@pytest.mark.parametrize("line", [
    "Allow any-user to read secret-bundles in tenancy",
    "Allow dynamic-group fr-finance-staging-runtime to manage all-resources in tenancy",
    "Allow dynamic-group fr-finance-staging-runtime to read secret-family in tenancy",
    "Allow dynamic-group fr-finance-staging-runtime to use keys in tenancy",
])
def test_iam_candidate_does_not_treat_unrelated_permissions_as_secret_bundle_read(line):
    assert not _CANDIDATE_STATEMENT.fullmatch(line)


def test_inert_script_returns_no_cloud_authorization(capsys):
    path = ROOT / "backend/scripts/aistudio_oci_iam_least_privilege_plan_only.py"
    spec = importlib.util.spec_from_file_location("m37350_iam_plan_only", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0
    output = capsys.readouterr().out
    assert "M37350_IAM_PLAN=PLAN_ONLY_PASS" in output
    assert "OCI_INSTANCE_OCID_AVAILABLE_FOR_PLAN=NO" in output
    assert "OCI_DYNAMIC_GROUP_CREATED=NO" in output
    assert "OCI_IAM_POLICY_CREATED=NO" in output
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in output
    assert "PIX_REAL=OFF" in output
    assert "ocid1." not in output
    assert "__" not in output


def test_static_plan_is_not_executable_oci_code():
    root = ROOT / "infra/oci/staging-reuse"
    assert not list(root.rglob("*.tf"))
    code = (
        ROOT / "backend/app/oci_iam_least_privilege_review.py"
    ).read_text() + (
        ROOT / "backend/scripts/aistudio_oci_iam_least_privilege_plan_only.py"
    ).read_text()
    for token in (
        "subprocess.", "os.system(", "requests.", "httpx.",
        "oci.identity.", "oci.key_management.", "oci.core.",
        "terraform apply", "create_dynamic_group(", "create_policy(",
        "update_policy(", "launch_instance(", "create_vault(",
        "get_secret_bundle(", "database_url", "psycopg.connect(",
    ):
        assert token not in code
