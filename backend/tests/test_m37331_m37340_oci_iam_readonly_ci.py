"""FR Finance M37331-M37340: OCI IAM SDK read-only inventory, mocked."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from app.oci_iam_readiness_readonly import (
    IAMReadOnlyBlocked,inspect_iam_readonly,
)

ROOT=Path(__file__).resolve().parents[2]
TEN="ocid1.tenancy.oc1.."+"a"*25
STAGE="ocid1.compartment.oc1.."+"b"*25
DG="ocid1.dynamicgroup.oc1.."+"c"*25
POL="ocid1.policy.oc1.."+"d"*25
POL2="ocid1.policy.oc1.."+"e"*25


def fixtures(*, groups=None,root_policies=None,staging_policies=None):
    if groups is None:
        groups=[{
            "id":DG,"name":"fr-finance-staging-instances",
            "lifecycle-state":"ACTIVE",
            "matching-rule":"ALL {instance.compartment.id = '"+STAGE+"'}",
        }]
    if root_policies is None:
        root_policies=[{
            "id":POL,"name":"fr-finance-staging-secret-reads",
            "compartment-id":TEN,"lifecycle-state":"ACTIVE",
            "statements":[
                "Allow dynamic-group fr-finance-staging-instances "
                "to read secret-bundles in compartment fr-finance-staging"
            ],
        }]
    if staging_policies is None:
        staging_policies=[{
            "id":POL2,"name":"fr-finance-audit",
            "compartment-id":STAGE,"lifecycle-state":"ACTIVE",
            "statements":["Allow group SecurityTeam to inspect secrets in compartment fr-finance-staging"],
        }]
    return {
        "compartment":[{"id":STAGE,"name":"fr-finance-staging","lifecycle-state":"ACTIVE"}],
        "dynamic-group":groups,
        "policy-root":root_policies,
        "policy-staging":staging_policies,
    }


def query_for(data):
    calls=[]
    def query(target,scope):
        calls.append((target,scope))
        assert scope == (STAGE if target=="policy-staging" else TEN)
        return data[target]
    return query,calls


def test_iam_candidates_never_become_attested_access():
    reader,calls=query_for(fixtures())
    audit=inspect_iam_readonly(TEN,"sa-saopaulo-1",reader)
    assert calls==[
        ("compartment",TEN),("dynamic-group",TEN),
        ("policy-root",TEN),("policy-staging",STAGE),
    ]
    assert audit.root_dynamic_groups_active==1
    assert audit.project_named_dynamic_groups_active==1
    assert audit.root_policies_active==1
    assert audit.staging_policies_active==1
    assert audit.candidate_secret_bundle_statements==1
    for name in (
        "workload_instance_principal_verified",
        "policy_effective_permissions_verified",
        "tenant_secret_isolation_verified",
        "vault_present_verified","real_secret_access_tested",
        "cloud_mutations_performed","deployment_authorized",
        "real_users_authorized","pix_real_authorized",
    ):
        assert getattr(audit,name) is False


def test_no_configured_groups_or_policies_still_valid_readonly():
    q,calls=query_for(fixtures(groups=[],root_policies=[],staging_policies=[]))
    audit=inspect_iam_readonly(TEN,"sa-saopaulo-1",q)
    assert audit.project_named_dynamic_groups_active==0
    assert audit.candidate_secret_bundle_statements==0
    assert not audit.policy_effective_permissions_verified


def test_different_group_name_not_project():
    g=fixtures()["dynamic-group"][0].copy()
    g["name"]="unrelated-team"
    q,_=query_for(fixtures(groups=[g]))
    assert inspect_iam_readonly(TEN,"sa-saopaulo-1",q).project_named_dynamic_groups_active==0


def test_tenancy_scoped_secret_read_is_review_candidate_not_proof():
    p=fixtures()["policy-root"][0].copy()
    p["statements"]=["Allow dynamic-group fr-finance-staging-instances to read secret-bundles in tenancy"]
    q,_=query_for(fixtures(root_policies=[p]))
    result=inspect_iam_readonly(TEN,"sa-saopaulo-1",q)
    # Broad candidate scan counts unfamiliar valid OCI policy syntax,
    # but NEVER attests effective permissions or authorizes deployment.
    assert result.candidate_secret_bundle_statements==1
    assert not result.policy_effective_permissions_verified
    assert not result.deployment_authorized


def test_unrelated_broad_tenancy_policy_is_only_manual_warning():
    p=fixtures()["policy-root"][0].copy()
    p["statements"]=["Allow any-group to manage secret-family in tenancy"]
    q,_=query_for(fixtures(root_policies=[p]))
    result=inspect_iam_readonly(TEN,"sa-saopaulo-1",q)
    assert result.overly_broad_secret_grants_manual_review
    assert not result.policy_effective_permissions_verified


@pytest.mark.parametrize("target",[
    "compartment","dynamic-group","policy-root","policy-staging",
])
def test_invalid_list_results_fail_closed(target):
    data=fixtures()
    data[target]=None
    query,_=query_for(data)
    with pytest.raises(IAMReadOnlyBlocked):
        inspect_iam_readonly(TEN,"sa-saopaulo-1",query)


@pytest.mark.parametrize("field,bad",[
    ("matching-rule",None),("id","invalid"),("lifecycle-state",None),
    ("name",12),
])
def test_malformed_group_schema_denied(field,bad):
    data=fixtures()
    data["dynamic-group"][0][field]=bad
    q,_=query_for(data)
    with pytest.raises(IAMReadOnlyBlocked,match="OCI_IAM_SCHEMA_INVALID"):
        inspect_iam_readonly(TEN,"sa-saopaulo-1",q)


@pytest.mark.parametrize("field,bad",[
    ("statements",None),("statements",[None]),("statements",[""]),
    ("id","not-ocid"),("compartment-id","wrong"),("name",False),
])
def test_malformed_policy_schema_denied(field,bad):
    data=fixtures()
    data["policy-staging"][0][field]=bad
    q,_=query_for(data)
    with pytest.raises(IAMReadOnlyBlocked,match="OCI_IAM_SCHEMA_INVALID"):
        inspect_iam_readonly(TEN,"sa-saopaulo-1",q)


def test_ambiguous_compartment_denied():
    data=fixtures()
    data["compartment"]*=2
    q,_=query_for(data)
    with pytest.raises(IAMReadOnlyBlocked,match="OCI_IAM_STAGING_COMPARTMENT_NOT_UNIQUE"):
        inspect_iam_readonly(TEN,"sa-saopaulo-1",q)


def test_wrong_tenancy_and_region_never_query():
    q,calls=query_for(fixtures())
    with pytest.raises(IAMReadOnlyBlocked,match="OCI_IAM_REGION_OR_TENANCY_DENIED"):
        inspect_iam_readonly("invalid","sa-saopaulo-1",q)
    with pytest.raises(IAMReadOnlyBlocked,match="OCI_IAM_REGION_OR_TENANCY_DENIED"):
        inspect_iam_readonly(TEN,"us-ashburn-1",q)
    assert calls==[]


def load_script():
    path=ROOT/"backend/scripts/aistudio_oci_iam_readonly.py"
    spec=importlib.util.spec_from_file_location("fr_iam_readonly",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeOCI:
    def __init__(self,monkeypatch,source,*,error=None,badstatus=200,pages=None):
        self.calls=[]
        outer=self
        class NoRetry: pass
        class IdentityClient:
            def __init__(self,config,**kw):
                assert config["region"]=="sa-saopaulo-1"
                assert kw["timeout"]==(5,30)
                assert isinstance(kw["retry_strategy"],NoRetry)
            def _list(self,target,compartment,**kwargs):
                outer.calls.append((target,compartment,kwargs))
                if error:
                    raise RuntimeError("SECRET PROVIDER ERROR: DO NOT PRINT")
                if target=="compartment":
                    assert compartment==TEN
                elif target=="dynamic-group":
                    assert compartment==TEN
                elif target=="policy-staging":
                    assert compartment==STAGE
                else:
                    assert compartment==TEN
                if pages:
                    idx=len(outer.calls)-1
                    return pages[idx]
                return SimpleNamespace(
                    status=badstatus,
                    data=[SimpleNamespace(**{
                        key.replace("-","_"):val
                        for key,val in row.items()
                    }) for row in source[target]],
                    next_page=None,
                )
            def list_compartments(self,compartment,**kwargs):
                return self._list("compartment",compartment,**kwargs)
            def list_dynamic_groups(self,compartment,**kwargs):
                return self._list("dynamic-group",compartment,**kwargs)
            def list_policies(self,compartment,**kwargs):
                return self._list("policy-root" if compartment==TEN else "policy-staging",compartment,**kwargs)
        sdk=SimpleNamespace(
            config=SimpleNamespace(from_file=lambda **kw:{"region":"sa-saopaulo-1","tenancy":TEN}),
            identity=SimpleNamespace(IdentityClient=IdentityClient),
            retry=SimpleNamespace(NoneRetryStrategy=NoRetry),
        )
        monkeypatch.setitem(sys.modules,"oci",sdk)
        self.sdk=sdk


def test_script_live_shape_mocked_with_sensitive_names_redacted(monkeypatch,capsys):
    fake=FakeOCI(monkeypatch,fixtures())
    assert load_script().main()==0
    lines=capsys.readouterr().out
    assert "M37340_IAM=READ_ONLY_PASS" in lines
    assert "OCI_PROJECT_NAMED_DYNAMIC_GROUPS_ACTIVE=1" in lines
    assert "OCI_CANDIDATE_SECRET_BUNDLE_STATEMENTS=1" in lines
    assert "OCI_EFFECTIVE_IAM_PERMISSIONS_ATTESTED=NO" in lines
    assert "OCI_SECRET_VALUES_READ=NO" in lines
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in lines
    for secret in (TEN,STAGE,DG,POL,POL2,"fr-finance-staging-secret-reads",
                   "ALL {instance.compartment.id","Allow dynamic-group"):
        assert secret not in lines
    assert len(fake.calls)==4


def test_script_http_non_200_fails_not_zero(monkeypatch,capsys):
    FakeOCI(monkeypatch,fixtures(),badstatus=403)
    assert load_script().main()==2
    assert "M37340_IAM=BLOCKED" in capsys.readouterr().out


def test_script_provider_exception_redacted(monkeypatch,capsys):
    FakeOCI(monkeypatch,fixtures(),error=True)
    assert load_script().main()==2
    output=capsys.readouterr().out
    assert "M37340_IAM=BLOCKED" in output
    assert "SECRET PROVIDER ERROR" not in output


def test_sdk_list_empty_http_200_is_valid(monkeypatch):
    fake=FakeOCI(monkeypatch,fixtures(groups=[]))
    result=load_script()._query(
        fake.sdk.identity.IdentityClient({"region":"sa-saopaulo-1"},timeout=(5,30),retry_strategy=fake.sdk.retry.NoneRetryStrategy()),
        fake.sdk,"dynamic-group",TEN,
    )
    assert result==[]


def test_sdk_pagination_through_two_pages(monkeypatch):
    page1=SimpleNamespace(status=200,data=[],next_page="CURSOR")
    item=SimpleNamespace(id=DG,name="fr-finance-staging-instances",
                         lifecycle_state="ACTIVE",matching_rule="match")
    page2=SimpleNamespace(status=200,data=[item],next_page=None)
    fake=FakeOCI(monkeypatch,fixtures(),pages=[page1,page2])
    result=load_script()._query(
        fake.sdk.identity.IdentityClient({"region":"sa-saopaulo-1"},timeout=(5,30),retry_strategy=fake.sdk.retry.NoneRetryStrategy()),
        fake.sdk,"dynamic-group",TEN,
    )
    assert len(result)==1 and result[0]["name"]=="fr-finance-staging-instances"
    assert fake.calls[1][2]["page"]=="CURSOR"


def test_sdk_repeated_pagination_fails_closed(monkeypatch):
    pages=[
        SimpleNamespace(status=200,data=[],next_page="REPEAT"),
        SimpleNamespace(status=200,data=[],next_page="REPEAT"),
    ]
    fake=FakeOCI(monkeypatch,fixtures(),pages=pages)
    with pytest.raises(IAMReadOnlyBlocked,match="OCI_IAM_PAGINATION_INVALID"):
        load_script()._query(
            fake.sdk.identity.IdentityClient({"region":"sa-saopaulo-1"},timeout=(5,30),retry_strategy=fake.sdk.retry.NoneRetryStrategy()),
            fake.sdk,"dynamic-group",TEN,
        )


def test_no_iam_write_methods_or_secret_bundle_calls():
    path=ROOT/"backend/scripts/aistudio_oci_iam_readonly.py"
    script=path.read_text()
    for danger in (
        "create_dynamic_group(","create_policy(","update_policy(",
        "delete_policy(","create_vault(","get_secret_bundle(",
        "create_secret(","launch_instance(","terraform apply",
        "set_policy(","activate_user(",
    ):
        assert danger not in script
    assert "OCI_SECRET_VALUES_READ=NO" in script
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in script
