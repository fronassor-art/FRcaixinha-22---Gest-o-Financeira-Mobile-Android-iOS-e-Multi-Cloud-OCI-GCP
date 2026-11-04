"""AI Studio M2800: read-only OCI Secret Retrieval (Instance Principal).

Real OCI SDK adapter, dormant until a deployed server calls it explicitly.
No OCI secret or private key is required on Termux; this module never writes
a secret, token, ledger or financial transaction.
"""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from typing import Any

CONTRACT = "AI_STUDIO_M2800_OCI_VAULT_MP_OAUTH_CONNECTORS_V1"
_OCID = re.compile(r"ocid1\.secret\.[A-Za-z0-9._-]{8,512}\Z")
_REGION = re.compile(r"[a-z][a-z0-9-]{3,50}\Z")
_MAX_SECRET_BYTES = 8192


class VaultUnavailable(RuntimeError):
    """Safe error: no secret value, OCI exception or identifier is logged."""


@dataclass(frozen=True)
class SecretValue:
    """No plaintext in repr, FastAPI responses or logs."""
    secret: str = field(repr=False)
    source: str = "OCI_SECRET_CURRENT"

    def __repr__(self) -> str:
        return "SecretValue(redacted=True, source=OCI_SECRET_CURRENT)"


def decode_current_oci_secret(*, secret_ocid: str, response: Any) -> SecretValue:
    """Decodes OCI get_secret_bundle response, without logging contents."""
    if type(secret_ocid) is not str or not _OCID.fullmatch(secret_ocid):
        raise VaultUnavailable("Invalid OCI secret reference")
    try:
        data = response.data
        current = data.secret_bundle_content
        if getattr(current, "content_type", "BASE64") != "BASE64":
            raise ValueError("Not BASE64")
        encoded = current.content
        if type(encoded) is not str or not 0 < len(encoded) <= 16000:
            raise ValueError("Encoded secret invalid")
        decoded = base64.b64decode(encoded, validate=True)
        if not 0 < len(decoded) <= _MAX_SECRET_BYTES:
            raise ValueError("Secret size invalid")
        value = decoded.decode("utf-8")
        if not value.strip() or "\x00" in value:
            raise ValueError("Invalid secret")
        return SecretValue(value)
    except (AttributeError, UnicodeError, ValueError, TypeError, binascii.Error):
        raise VaultUnavailable("OCI secret unavailable") from None


def get_current_secret(*, secret_ocid: str, client: Any) -> SecretValue:
    """Use already-authorized OCI SDK SecretsClient, never user API keys.

    The caller must derive secret_ocid from tenant-scoped server-side storage;
    client-supplied OCIDs must NEVER be accepted by an HTTP endpoint.
    """
    if type(secret_ocid) is not str or not _OCID.fullmatch(secret_ocid):
        raise VaultUnavailable("Invalid OCI secret reference")
    try:
        response = client.get_secret_bundle(secret_ocid, stage="CURRENT")
    except Exception:
        raise VaultUnavailable("OCI secret unavailable") from None
    return decode_current_oci_secret(secret_ocid=secret_ocid, response=response)


def build_instance_principal_secrets_client(*, region: str, enabled: bool = False):
    """REAL OCI SDK client factory; opt-in only on provisioned OCI Compute.

    Requires SDK 'oci' installed in the OCI server and dynamic-group policy
    allowing read of specific secrets; never uses ~/.oci/config/API key.
    """
    if (enabled is not True or type(region) is not str
            or not _REGION.fullmatch(region)):
        raise VaultUnavailable("OCI instance-principal client not enabled")
    try:
        import oci  # optional dependency installed only on authorized OCI server
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        client = oci.secrets.SecretsClient(
            config={"region": region}, signer=signer,
        )
    except Exception:
        raise VaultUnavailable("OCI instance-principal unavailable") from None
    return client
