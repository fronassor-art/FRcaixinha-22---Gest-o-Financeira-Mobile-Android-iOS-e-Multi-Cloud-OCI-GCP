"""M26900 — restricted OCI Vault Secrets key adapter for encrypted envelopes.

OCI Vault *Secrets* holds a 32-byte AES-256 key as a Base64 secret value.
The SDK itself is optional and loaded only on explicitly approved OCI
compute via instance principals; never use a local API key fallback.
No real OCI requests are performed by CI and no user secrets are committed.
Use this provider with M26800 tenant-scoped key policy to authorize tenants.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import re
from typing import Any, Mapping

from .delivery_envelope import EnvelopeBlocked

_ALIAS_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{3,79}\Z")
_OCID_RE = re.compile(
    r"ocid1\.vaultsecret\.oc1\.[a-z0-9-]+\.[A-Za-z0-9]{20,256}\Z"
)
_MAX_B64 = 80


class VaultKeyUnavailable(ValueError):
    """Neutral error: no OCI secret value, response or OCID is disclosed."""


@dataclass(frozen=True, repr=False)
class SecretVersionRef:
    """Non-secret operator-reviewed reference. Never contains key material."""

    key_alias: str
    secret_ocid: str
    version_number: int

    def __repr__(self) -> str:
        return "SecretVersionRef(redacted=True)"


def _reject() -> VaultKeyUnavailable:
    return VaultKeyUnavailable("M26900_VAULT_KEY_UNAVAILABLE")


class OciVaultKeyProvider:
    """KeyProvider boundary using injected SecretsClient, never default creds.

    Strict version pinning prohibits a CURRENT-stage swap changing an
    existing envelope's key between writes and reads.
    """

    def __init__(self, *, client: Any, references: Mapping[str, SecretVersionRef]):
        if client is None or type(references) is not dict or not references:
            raise _reject()
        if not callable(getattr(client, "get_secret_bundle", None)):
            raise _reject()
        self._client = client
        self._references = dict(references)
        for alias, ref in self._references.items():
            if (type(alias) is not str or not _ALIAS_RE.fullmatch(alias)
                    or not isinstance(ref, SecretVersionRef)
                    or alias != ref.key_alias
                    or type(ref.secret_ocid) is not str
                    or not _OCID_RE.fullmatch(ref.secret_ocid)
                    or type(ref.version_number) is not int
                    or not 1 <= ref.version_number <= 1_000_000_000):
                raise _reject()

    def __repr__(self) -> str:
        return "OciVaultKeyProvider(credentialless=True, redacted=True)"

    def load_key(self, key_id: str) -> bytes:
        if type(key_id) is not str:
            raise _reject()
        pointer = self._references.get(key_id)
        if pointer is None:
            raise _reject()
        try:
            response = self._client.get_secret_bundle(
                secret_id=pointer.secret_ocid,version_number=pointer.version_number,
            )
            bundle = response.data
            contents = bundle.secret_bundle_content
            if (bundle.secret_id != pointer.secret_ocid
                    or type(bundle.version_number) is not int
                    or bundle.version_number != pointer.version_number
                    or contents.content_type != "BASE64"
                    or type(contents.content) is not str
                    or not 1 <= len(contents.content) <= _MAX_B64):
                raise _reject()
            key = base64.b64decode(contents.content,validate=True)
            if len(key) != 32 or base64.b64encode(key).decode("ascii") != contents.content:
                raise _reject()
            return key
        except Exception:
            raise _reject() from None


def build_instance_principals_secrets_client(*, operator_oci_approved: bool) -> Any:
    """Only OCI compute with explicitly approved IAM can instantiate client.

    No config-file fallback, API keys, resource-principal auto-discovery or
    environment-secret fallback. Host identity must already be provisioned.
    """
    if operator_oci_approved is not True:
        raise _reject()
    try:
        import oci  # type: ignore[import-not-found]
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        return oci.secrets.SecretsClient({}, signer=signer, timeout=(3, 10))
    except Exception:
        raise _reject() from None
