"""M27300: HMAC index rejects offline email guessing without secret key."""
from dataclasses import replace
from hashlib import sha256
from uuid import UUID, uuid4

import pytest

from app.recipient_index_guard import (
    RecipientIndexBlocked, RecipientIndex,
    build_recipient_index, matches_recipient_index,
)


ALIAS="ci-index-key-2026-v1"
ADDRESS="member@example.com"


class SyntheticIndexKeyProvider:
    def __init__(self, key=b"J"*32):
        self.key=key
        self.calls=[]
    def load_index_key(self, tenant_id, key_alias):
        self.calls.append((tenant_id,key_alias))
        assert key_alias==ALIAS
        return self.key


def fixture():
    tenant=uuid4()
    provider=SyntheticIndexKeyProvider()
    index=build_recipient_index(
        tenant_id=tenant,recipient=ADDRESS,key_alias=ALIAS,
        provider=provider,
    )
    return tenant,provider,index


def test_hmac_index_is_not_plain_sha256_email_and_works_for_same_scope():
    tenant,provider,index=fixture()
    assert len(index.digest)==64
    assert index.digest!=sha256(ADDRESS.encode()).hexdigest()
    assert ADDRESS not in repr(index)
    assert ALIAS not in repr(index)
    assert index.version==1
    assert matches_recipient_index(
        index=index,tenant_id=tenant,recipient=ADDRESS,
        key_alias=ALIAS,provider=provider,
    )
    assert matches_recipient_index(
        index=index,tenant_id=tenant,recipient="MEMBER@EXAMPLE.COM",
        key_alias=ALIAS,provider=provider,
    )
    assert not matches_recipient_index(
        index=index,tenant_id=tenant,recipient="different@example.com",
        key_alias=ALIAS,provider=provider,
    )


def test_cross_tenant_digest_and_scope_swap_fails_closed():
    tenant,provider,index=fixture()
    other=uuid4()
    other_index=build_recipient_index(
        tenant_id=other,recipient=ADDRESS,key_alias=ALIAS,provider=provider,
    )
    assert other_index.digest!=index.digest
    with pytest.raises(RecipientIndexBlocked):
        matches_recipient_index(
            index=index,tenant_id=other,recipient=ADDRESS,
            key_alias=ALIAS,provider=provider,
        )


def test_different_tenant_key_or_rotation_changes_index():
    tenant,provider,index=fixture()
    rotated=SyntheticIndexKeyProvider(b"R"*32)
    newer=build_recipient_index(
        tenant_id=tenant,recipient=ADDRESS,key_alias=ALIAS,provider=rotated,
    )
    assert newer.digest!=index.digest
    assert not matches_recipient_index(
        index=index,tenant_id=tenant,recipient=ADDRESS,
        key_alias=ALIAS,provider=rotated,
    )


@pytest.mark.parametrize("recipient", [
    "", "bad", "not-an-email", "x@example.com\nBcc:evil@example.com",
    " x@example.com", "x@example.com ", "x@example.com?cc=evil@example.com",
])
def test_invalid_recipient_is_never_indexed(recipient):
    tenant,provider,_=fixture()
    with pytest.raises(RecipientIndexBlocked):
        build_recipient_index(
            tenant_id=tenant,recipient=recipient,
            key_alias=ALIAS,provider=provider,
        )


@pytest.mark.parametrize("key", [b"short",b"R"*31,b"Z"*33,"R"*32,None])
def test_invalid_index_key_rejected(key):
    tenant,_,_=fixture()
    with pytest.raises(RecipientIndexBlocked):
        build_recipient_index(
            tenant_id=tenant,recipient=ADDRESS,key_alias=ALIAS,
            provider=SyntheticIndexKeyProvider(key),
        )


def test_key_provider_error_never_exposes_sensitive_error():
    class Failing:
        def load_index_key(self,tenant_id,key_alias):
            raise RuntimeError("SENSITIVE_VAULT_TOKEN")
    with pytest.raises(RecipientIndexBlocked) as error:
        build_recipient_index(
            tenant_id=uuid4(),recipient=ADDRESS,key_alias=ALIAS,provider=Failing(),
        )
    assert "SENSITIVE_VAULT_TOKEN" not in str(error.value)
    assert ADDRESS not in str(error.value)


def test_tampered_digest_key_id_and_version_rejected():
    tenant,provider,index=fixture()
    for change in (
        {"digest":"0"*64}, {"digest":"Z"*64},
        {"key_alias":"wrong-other-key-v2"}, {"version":2},
        {"tenant_id":UUID(int=0)},
    ):
        candidate=replace(index,**change)
        if change.get("digest")=="0"*64:
            assert not matches_recipient_index(
                index=candidate,tenant_id=tenant,recipient=ADDRESS,
                key_alias=ALIAS,provider=provider,
            )
        else:
            with pytest.raises(RecipientIndexBlocked):
                matches_recipient_index(
                    index=candidate,tenant_id=tenant,recipient=ADDRESS,
                    key_alias=ALIAS,provider=provider,
                )


def test_zero_tenant_and_invalid_alias_are_blocked():
    with pytest.raises(RecipientIndexBlocked):
        build_recipient_index(
            tenant_id=UUID(int=0),recipient=ADDRESS,key_alias=ALIAS,
            provider=SyntheticIndexKeyProvider(),
        )
    with pytest.raises(RecipientIndexBlocked):
        build_recipient_index(
            tenant_id=uuid4(),recipient=ADDRESS,key_alias="x",
            provider=SyntheticIndexKeyProvider(),
        )


def test_no_public_routes_or_network_and_no_reuse_of_aes_key_provider():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    code=(root/"backend/app/recipient_index_guard.py").read_text()
    for forbidden in ("os.getenv", "os.environ", "oci.config", "smtplib",
                      "requests.", "httpx.", "INSERT INTO", "UPDATE public.",
                      "load_key(", "private_key", "logger.", "print("):
        assert forbidden not in code
    assert "load_index_key(" in code
    assert "hmac.new" in code
    assert "hmac.compare_digest" in code
    for route in ("auth.py","invitations.py","master.py"):
        public=(root/"backend/app/routers"/route).read_text()
        assert "build_recipient_index" not in public
