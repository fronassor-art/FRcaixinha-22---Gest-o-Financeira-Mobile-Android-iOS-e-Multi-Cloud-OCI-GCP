"""Testa provisionamento só em banco local descartável do CI."""
import os
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pytest
from app.provisioning import create_tenant_account
from app.security import verify_password_secure


@pytest.mark.skipif(os.getenv("FRCAIXINHA_CI_ISOLATED") != "1", reason="Somente banco isolado de CI")
def test_separate_admin_and_member_credentials():
    dsn = os.environ["CI_ADMIN_DATABASE_URL"]
    parsed = urlparse(dsn)
    assert parsed.hostname in ("127.0.0.1", "localhost") and parsed.path == "/frcaixinha_ci"
    owner, tenant = uuid4(), uuid4()
    created = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        try:
            conn.execute("INSERT INTO users (id,email,full_name,cpf,phone) VALUES (%s,%s,%s,%s,%s)",
                         (owner, f"{owner}@example.invalid", "Pessoa de teste", owner.hex[:14], "00000000000"))
            conn.execute("INSERT INTO tenants (id,display_name,contracting_party_id,admin_user_id) VALUES (%s,%s,%s,%s)",
                         (tenant, "Caixinha temporária", str(uuid4()), owner))
            for role in ("TENANT_ADMIN", "TENANT_MEMBER"):
                marker = uuid4()
                password = f"senha-de-teste-{marker}"
                values = dict(email=f"{marker}@example.invalid", full_name="Conta temporária", cpf=marker.hex[:14],
                              phone="00000000000", password=password, tenant_id=tenant, role=role)
                user_id, membership_id = create_tenant_account(conn, **values)
                created.append(user_id)
                row = conn.execute("SELECT c.password_hash, u.is_master, m.role, m.tenant_id FROM users u JOIN credentials c ON c.user_id=u.id JOIN memberships m ON m.user_id=u.id WHERE m.id=%s", (membership_id,)).fetchone()
                assert row and row[0] != password and verify_password_secure(password, row[0])
                assert row[1:] == (False, role, tenant)
                with pytest.raises(ValueError, match="já cadastrado"):
                    create_tenant_account(conn, **values)
            count = conn.execute("SELECT count(*) FROM memberships WHERE tenant_id=%s", (tenant,)).fetchone()[0]
            assert count == 2
        finally:
            conn.execute("DELETE FROM tenants WHERE id=%s", (tenant,))
            conn.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", ([owner, *created],))
