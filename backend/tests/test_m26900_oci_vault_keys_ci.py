"""M26900 — OCI Vault Secrets client contract mocked: zero network or real keys."""
import base64
from dataclasses import replace
from types import SimpleNamespace
import sys
from uuid import uuid4

import pytest

from app.delivery_envelope import DeliveryScope,DeliverySecret
from app.delivery_key_lifecycle import (
    KeyLifecycle,KeyMetadata,TenantKeyCatalog,
    seal_with_key_policy,open_with_key_policy,
)
from app.oci_vault_envelope_keys import (
    VaultKeyUnavailable,OciVaultKeyProvider,SecretVersionRef,
    build_instance_principals_secrets_client,
)

OCID="ocid1.vaultsecret.oc1.sa-saopaulo-1."+"a"*48
ALIAS="ci-tenant-key-2026-v1"
VERSION=7
NOW=1794000000


def ref():
    return SecretVersionRef(ALIAS,OCID,VERSION)


class FakeSecretsClient:
    def __init__(self, *, raw=b"K"*32,content_type="BASE64",
                 returned_version=VERSION, returned_ocid=OCID,
                 error=False):
        self.raw=raw
        self.content_type=content_type
        self.returned_version=returned_version
        self.returned_ocid=returned_ocid
        self.error=error
        self.calls=[]
    def get_secret_bundle(self, *, secret_id,version_number):
        self.calls.append((secret_id,version_number))
        if self.error:
            raise RuntimeError("sensitive internal OCI error with secret details")
        return SimpleNamespace(data=SimpleNamespace(
            secret_id=self.returned_ocid,
            version_number=self.returned_version,
            secret_bundle_content=SimpleNamespace(
                content_type=self.content_type,
                content=base64.b64encode(self.raw).decode("ascii"),
            ),
        ))


def test_exact_version_and_base64_content_delivers_only_32_bytes():
    client=FakeSecretsClient()
    service=OciVaultKeyProvider(client=client,references={ALIAS:ref()})
    assert service.load_key(ALIAS)==b"K"*32
    assert client.calls==[(OCID,VERSION)]
    assert OCID not in repr(service)
    assert OCID not in repr(ref())
    assert b"K"*32 != repr(service).encode()


@pytest.mark.parametrize("changed",[
    {"raw":b"short"},
    {"raw":b"A"*31},
    {"raw":b"Z"*33},
    {"content_type":"UNKNOWN_ENUM_VALUE"},
    {"content_type":"PLAIN_TEXT"},
    {"returned_version":VERSION+1},
    {"returned_ocid":"ocid1.vaultsecret.oc1.iad."+"b"*40},
    {"error":True},
])
def test_bad_bundle_or_failed_oci_call_never_leaks_or_falls_back(changed):
    service=OciVaultKeyProvider(
        client=FakeSecretsClient(**changed), references={ALIAS:ref()},
    )
    with pytest.raises(VaultKeyUnavailable) as exc:
        service.load_key(ALIAS)
    assert "sensitive internal" not in str(exc.value)
    assert OCID not in str(exc.value)


@pytest.mark.parametrize("invalid",[
    "", "short", "wrong", "ocid1.vaultsecret.oc1.iad.abc",
    "ocid1.vaultsecret.oc1.iad."+"$"*48,
])
def test_invalid_secret_references_fail_closed(invalid):
    with pytest.raises(VaultKeyUnavailable):
        OciVaultKeyProvider(
            client=FakeSecretsClient(),
            references={ALIAS:SecretVersionRef(ALIAS,invalid,VERSION)},
        )


@pytest.mark.parametrize("invalid",[0,-1,True,"7",1000000001])
def test_unpinned_or_invalid_versions_forbidden(invalid):
    with pytest.raises(VaultKeyUnavailable):
        OciVaultKeyProvider(
            client=FakeSecretsClient(),
            references={ALIAS:SecretVersionRef(ALIAS,OCID,invalid)},
        )


def test_unknown_alias_does_not_contact_vault():
    client=FakeSecretsClient()
    service=OciVaultKeyProvider(client=client,references={ALIAS:ref()})
    with pytest.raises(VaultKeyUnavailable):
        service.load_key("another-tenant-key")
    assert client.calls==[]


def test_key_lifecycle_and_vault_adapter_authenticates_aes_payload_offline():
    tenant=uuid4()
    scope=DeliveryScope(
        tenant_id=tenant,event_id=uuid4(),document_id=uuid4(),
        target_role="TENANT_MEMBER",purpose="INVITATION",
        issued_at=NOW,expires_at=NOW+600,
    )
    metadata=KeyMetadata(
        key_id=ALIAS,tenant_id=tenant,lifecycle=KeyLifecycle.ACTIVE,
        active_from=NOW-60,encrypt_until=NOW+300,decrypt_until=NOW+1000,
    )
    catalog=TenantKeyCatalog({ALIAS:metadata})
    client=FakeSecretsClient()
    vault=OciVaultKeyProvider(client=client,references={ALIAS:ref()})
    payload=DeliverySecret("ci-member@example.com","C"*48)
    envelope=seal_with_key_policy(
        scope=scope,secret=payload,key_id=ALIAS,
        catalog=catalog,provider=vault,now=NOW,
    )
    assert open_with_key_policy(
        envelope=envelope,scope=scope,catalog=catalog,
        provider=vault,now=NOW+10,
    )==payload
    assert client.calls==[(OCID,VERSION),(OCID,VERSION)]


def test_explicit_oci_approval_required_even_without_sdk():
    with pytest.raises(VaultKeyUnavailable):
        build_instance_principals_secrets_client(operator_oci_approved=False)


def test_instance_principal_builder_does_not_read_api_key_files(monkeypatch):
    signer=object()
    invoked=[]
    class FakeSigners:
        @staticmethod
        def InstancePrincipalsSecurityTokenSigner():
            invoked.append("SIGNER")
            return signer
    def make_client(config,*,signer,timeout):
        invoked.append((config,signer,timeout))
        return "CI_MOCK_CLIENT_NO_NETWORK"
    mock=SimpleNamespace(
        auth=SimpleNamespace(signers=FakeSigners),
        secrets=SimpleNamespace(SecretsClient=make_client),
    )
    monkeypatch.setitem(sys.modules,"oci",mock)
    assert build_instance_principals_secrets_client(
        operator_oci_approved=True,
    )=="CI_MOCK_CLIENT_NO_NETWORK"
    assert invoked==["SIGNER",({},signer,(3,10))]


def test_no_public_route_uses_oci_client_or_materialized_key():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    body=(root/"backend/app/oci_vault_envelope_keys.py").read_text()
    for forbidden in (
        "from_file(", "oci.config", "api_key", "private_key",
        "os.environ", "os.getenv", "print(", "logger.", "logging.",
        "get_secret_bundle_by_name", "stage='CURRENT'", "stage='LATEST'",
    ):
        assert forbidden not in body
    assert "InstancePrincipalsSecurityTokenSigner()" in body
    assert "version_number=pointer.version_number" in body
    for name in ("auth.py","invitations.py","master.py"):
        public=(root/"backend/app/routers"/name).read_text()
        assert "OciVaultKeyProvider" not in public
        assert "build_instance_principals_secrets_client" not in public
