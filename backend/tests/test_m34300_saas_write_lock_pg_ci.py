"""M34300 PG integration: no raw or SECURITY DEFINER member/quota writes."""
import os
import pytest

TA="daba0000-0000-4000-8000-000000000010"
A="daba0000-0000-4000-8000-000000000001"
MEMBERSHIP_A="daba0000-0000-4000-8000-000000000011"

def test_app_role_cannot_bypass_member_and_quota_write_barrier():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("Disposable GitHub CI only")
    url=os.getenv("CI_SAAS_WRITE_GATE_APP_URL")
    owner_url=os.getenv("CI_SAAS_WRITE_GATE_ADMIN_URL")
    if not url or not owner_url:
        pytest.fail("Missing disposable CI database connection")
    import psycopg
    with psycopg.connect(owner_url) as owner:
        for tbl in ("memberships","quotas"):
            assert owner.execute(
                "SELECT relrowsecurity AND relforcerowsecurity "
                "FROM pg_class WHERE oid=%s::regclass",
                ("public."+tbl,)).fetchone()[0] is True
            for role in ("frcaixinha_app_role","frcaixinha_auth_role",
                         "frcaixinha_saas_admission_ci"):
                for operation in ("INSERT","UPDATE","DELETE","TRUNCATE"):
                    assert owner.execute(
                        "SELECT has_table_privilege(%s,%s,%s)",
                        (role,"public."+tbl,operation)).fetchone()[0] is False
        baseline=owner.execute(
            "SELECT (SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas),"
            "(SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.ledger_entries)"
        ).fetchone()
        # Explicit CI-only probe models an old callable SECURITY DEFINER
        # function that could circumvent the revoked table permissions.
        owner.execute("""
          CREATE FUNCTION public.m34300_ci_definer_bypass_probe(kind text)
          RETURNS void LANGUAGE plpgsql SECURITY DEFINER
          SET search_path=pg_catalog,public,pg_temp AS $fn$
          BEGIN
            IF current_database()<>'frcaixinha_staging'
              THEN RAISE EXCEPTION 'M34300_PROBE_DISPOSABLE_ONLY'; END IF;
            IF kind='MEMBER' THEN
              INSERT INTO public.memberships(tenant_id,user_id,role)
              VALUES ('daba0000-0000-4000-8000-000000000010',
                      'daba0000-0000-4000-8000-000000000001','TENANT_MEMBER');
            ELSIF kind='QUOTA' THEN
              INSERT INTO public.quotas(tenant_id,membership_id,quota_number,value_brl)
              VALUES ('daba0000-0000-4000-8000-000000000010',
                      'daba0000-0000-4000-8000-000000000011',33333,150.00);
            ELSE RAISE EXCEPTION 'M34300_UNKNOWN_PROBE'; END IF;
          END $fn$;
        """)
        owner.execute(
            "REVOKE ALL ON FUNCTION public.m34300_ci_definer_bypass_probe(text) FROM PUBLIC")
        owner.execute(
            "GRANT EXECUTE ON FUNCTION public.m34300_ci_definer_bypass_probe(text) "
            "TO frcaixinha_saas_admission_ci")
    statements=[
        ("INSERT INTO public.memberships(tenant_id,user_id,role)"
         " VALUES (%s,%s,'TENANT_MEMBER')",(TA,A)),
        ("UPDATE public.memberships SET status='SUSPENSA' WHERE tenant_id=%s",(TA,)),
        ("DELETE FROM public.memberships WHERE tenant_id=%s",(TA,)),
        ("INSERT INTO public.quotas(tenant_id,membership_id,quota_number,value_brl)"
         " VALUES (%s,%s,33333,150.00)",(TA,MEMBERSHIP_A)),
        ("UPDATE public.quotas SET status='INATIVA' WHERE tenant_id=%s",(TA,)),
        ("DELETE FROM public.quotas WHERE tenant_id=%s",(TA,)),
        ("SELECT public.m34300_ci_definer_bypass_probe('MEMBER')",()),
        ("SELECT public.m34300_ci_definer_bypass_probe('QUOTA')",()),
    ]
    for statement,args in statements:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(url) as app:
                with app.transaction():
                    app.execute("SELECT set_config('app.current_user_id',%s,true)",(A,))
                    app.execute("SELECT set_config('app.current_tenant_id',%s,true)",(TA,))
                    app.execute("SELECT set_config('app.current_role','TENANT_ADMIN',true)")
                    app.execute(statement,args)
    with psycopg.connect(owner_url) as owner:
        after=owner.execute(
            "SELECT (SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas),"
            "(SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.ledger_entries)"
        ).fetchone()
        assert baseline==after
        for tbl,trigger in (
            ("memberships","memberships_unlicensed_write_lock"),
            ("quotas","quotas_unlicensed_write_lock"),
        ):
            assert owner.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_trigger WHERE "
                "tgrelid=%s::regclass AND tgname=%s AND tgenabled='O')",
                ("public."+tbl,trigger)).fetchone()[0] is True
