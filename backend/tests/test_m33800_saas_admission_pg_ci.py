"""M33800: restricted plan visibility in disposable PG18 staging."""
import os
from uuid import UUID
import pytest

A="daba0000-0000-4000-8000-000000000001"
B="daba0000-0000-4000-8000-000000000002"
TA="daba0000-0000-4000-8000-000000000010"
TB="daba0000-0000-4000-8000-000000000020"

def test_plan_tier_read_only_for_licensed_tenant_admin():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("Postgres disposable CI only")
    url=os.getenv("CI_SAAS_ADMISSION_APP_URL")
    admin_url=os.getenv("CI_SAAS_ADMISSION_ADMIN_URL")
    if not url or not admin_url:
        pytest.fail("Disposable CI DSN missing")
    import psycopg
    with psycopg.connect(admin_url) as admin:
        assert admin.execute("SELECT to_regclass('public.platform_license_plans') IS NOT NULL").fetchone()[0] is True
        assert admin.execute("SELECT EXISTS(SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='platform_license_plans' AND policyname='platform_license_plans_admin_licensed_read')").fetchone()[0] is True
        assert admin.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id=%s",(TA,)).fetchone()[0]==1
        for table in ("saas_license_entitlements","saas_payment_intents"):
            assert admin.execute("SELECT has_table_privilege('frcaixinha_app_role',%s,'INSERT')",("public."+table,)).fetchone()[0] is False
    def read_plan(user,tenant,role="TENANT_ADMIN"):
        with psycopg.connect(url) as conn:
            with conn.transaction():
                conn.execute("SELECT set_config('app.current_user_id',%s,true)",(user,))
                conn.execute("SELECT set_config('app.current_tenant_id',%s,true)",(tenant,))
                conn.execute("SELECT set_config('app.current_role',%s,true)",(role,))
                return conn.execute("SELECT tier,members_limit,quotas_limit FROM public.platform_license_plans ORDER BY tier").fetchall()
    assert read_plan(A,TA)==[("ESSENCIAL",20,40)]
    assert read_plan(A,TB)==[]
    assert read_plan(B,TB)==[]
    assert read_plan(A,TA,"TENANT_MEMBER")==[]
    assert read_plan(B,TA)==[]
    with psycopg.connect(url) as conn:
        with pytest.raises(psycopg.Error):
            with conn.transaction():
                conn.execute("INSERT INTO public.platform_license_plans(tier,display_name,members_limit,quotas_limit,status) VALUES('X','X',1,1,'ACTIVE')")
