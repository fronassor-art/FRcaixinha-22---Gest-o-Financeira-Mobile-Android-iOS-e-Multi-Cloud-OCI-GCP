"""M37450 — original PG18 licensed-access inventory, SELECT-only.

Intentionally does not infer entitlement from a plan or a payment status.
"""
from __future__ import annotations
from dataclasses import dataclass

IDENTITY_SQL="""SELECT current_database(),session_user,current_user,
inet_server_port(),current_setting('data_directory'),
current_setting('server_version_num')::int,current_setting('transaction_read_only')"""

LICENSING_SQL="""SELECT
 (SELECT count(*)::int FROM public.tenants),
 (SELECT count(*)::int FROM public.tenants WHERE status='ATIVO'),
 (SELECT count(*)::int FROM public.memberships),
 (SELECT count(*)::int FROM public.platform_license_plans),
 (SELECT count(*)::int FROM public.platform_license_plans WHERE status='ACTIVE'),
 (SELECT count(*)::int FROM public.platform_license_price_versions),
 (SELECT count(*)::int FROM public.saas_subscription_preparations),
 (SELECT count(*)::int FROM public.saas_payment_intents),
 (SELECT count(*)::int FROM public.saas_payment_intents WHERE status='APPROVED'),
 (SELECT count(*)::int FROM public.saas_license_entitlements),
 (SELECT count(*)::int FROM public.saas_license_entitlements
   WHERE status='ACTIVE'),
 (SELECT count(*)::int FROM public.saas_license_entitlements e
   JOIN public.tenants t ON t.id=e.tenant_id
   WHERE e.status='ACTIVE' AND t.status='ATIVO'
   AND e.valid_from<=now() AND e.valid_until>now()),
 (SELECT count(*)::int FROM public.saas_license_entitlements e
   JOIN public.saas_subscription_preparations s
   ON s.id=e.preparation_id
   JOIN public.saas_payment_intents p
   ON p.id=e.payment_intent_id
   WHERE e.tenant_id<>s.tenant_id OR e.tenant_id<>p.tenant_id
      OR s.tenant_id<>p.tenant_id),
 (SELECT count(*)::int FROM public.cycles),
 (SELECT count(*)::int FROM public.contributions),
 (SELECT count(*)::int FROM public.pix_payment_intents),
 (SELECT count(*)::int FROM public.ledger_transactions)
"""

SECURITY_SQL="""SELECT
 (SELECT count(*)::int FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND
     c.relname IN('saas_payment_intents','saas_license_entitlements',
       'saas_subscription_preparations')
   AND c.relrowsecurity AND c.relforcerowsecurity),
 has_table_privilege('frcaixinha_app_role',
    'public.saas_license_entitlements','SELECT'),
 has_table_privilege('frcaixinha_app_role',
    'public.saas_license_entitlements','INSERT'),
 has_table_privilege('frcaixinha_app_role',
    'public.saas_license_entitlements','UPDATE'),
 has_table_privilege('frcaixinha_auth_role',
    'public.saas_license_entitlements','INSERT'),
 has_table_privilege('frcaixinha_app_role',
    'public.saas_payment_intents','INSERT'),
 has_table_privilege('frcaixinha_auth_role',
    'public.saas_payment_intents','INSERT')
"""

COUNTS=("TENANTS","ACTIVE_TENANTS","MEMBERSHIPS","CATALOG_PLANS",
 "ACTIVE_CATALOG_PLANS","PRICE_VERSIONS","SUBSCRIPTION_PREPARATIONS",
 "PAYMENT_INTENTS","APPROVED_PAYMENT_ROWS","ENTITLEMENTS",
 "ACTIVE_ENTITLEMENT_ROWS","CURRENT_ACTIVE_TENANT_ENTITLEMENTS",
 "CROSS_TENANT_ENTITLEMENT_LINKS","CYCLES","CONTRIBUTIONS",
 "PIX_PAYMENT_INTENTS","LEDGER_TRANSACTIONS")
SECURITY_EXPECTED=(3,True,False,False,False,False,False)

class LicenseInventoryBlocked(ValueError):pass
@dataclass(frozen=True)
class LicenseInventory:
    counts:tuple[int,...]
    security:tuple

def validate(counts,security):
    if(type(counts) is not tuple or len(counts)!=len(COUNTS) or
       any(type(n) is not int or not 0<=n<=100000000 for n in counts)):
        raise LicenseInventoryBlocked("INVALID_LICENSE_COUNTS")
    if(type(security) is not tuple or
       len(security)!=len(SECURITY_EXPECTED) or
       type(security[0]) is not int or
       any(type(v) is not bool for v in security[1:])):
        raise LicenseInventoryBlocked("INVALID_LICENSE_SECURITY_RESPONSE")
    if security!=SECURITY_EXPECTED:
        raise LicenseInventoryBlocked("LICENSE_RLS_OR_GRANTS_UNSAFE")
    if counts[0:3]!=(1,1,2):
        raise LicenseInventoryBlocked("ORIGINAL_TENANT_MEMBERSHIP_BASELINE_CHANGED")
    if counts[3]<2 or counts[4]<1 or counts[5]<2:
        raise LicenseInventoryBlocked("LICENSE_CATALOG_INCOMPLETE")
    if counts[12]!=0:
        raise LicenseInventoryBlocked("CROSS_TENANT_LICENSE_LINKS")
    if any(counts[i] for i in (13,14,15,16)):
        raise LicenseInventoryBlocked("UNEXPECTED_FINANCIAL_DATA")
    if counts[10]>counts[9] or counts[11]>counts[10] or counts[8]>counts[7]:
        raise LicenseInventoryBlocked("INVALID_LICENSE_COUNTS_RELATION")
    return LicenseInventory(counts,security)

def examine(conn):
    try:
        identity=conn.execute(IDENTITY_SQL).fetchone()
    except Exception:
        raise LicenseInventoryBlocked("ORIGINAL_PG18_IDENTITY_READ_FAILED") from None
    if(type(identity) is not tuple or len(identity)!=7 or
        identity[:5]!=("frcaixinha_aistudio_dev","frc_ai_owner","frc_ai_owner",
        5433,"/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18") or
        type(identity[5]) is not int or not 180000<=identity[5]<190000 or
        identity[6]!="on"):
        raise LicenseInventoryBlocked("WRONG_OR_WRITABLE_PG18")
    try:
        counts=conn.execute(LICENSING_SQL).fetchone()
        security=conn.execute(SECURITY_SQL).fetchone()
    except Exception:
        raise LicenseInventoryBlocked("LICENSE_CATALOG_READ_FAILED") from None
    return validate(counts,security)

def report(e):
    if not isinstance(e,LicenseInventory):
        raise LicenseInventoryBlocked("INVALID_REPORT")
    c=e.counts
    state=(
      "NO_ENTITLEMENT_RECORDED" if c[9]==0 else
      "ENTITLEMENT_EXISTS_REQUIRES_INDEPENDENT_PAYMENT_ATTESTATION"
    )
    return (
      "=== FR FINANCE M37450 ORIGINAL PG18 LICENSE INVENTORY READ ONLY ===",
      "M37450_STATUS=READ_ONLY_PASS",
      "M37450_TENANT=1_ACTIVE",
      "M37450_MEMBERSHIPS=2_PRESERVED",
      "M37450_LICENSE_CATALOG_PLANS="+str(c[3]),
      "M37450_LICENSE_PRICE_VERSIONS="+str(c[5]),
      "M37450_SUBSCRIPTION_PREPARATIONS="+str(c[6]),
      "M37450_PAYMENT_INTENTS="+str(c[7]),
      "M37450_APPROVED_PAYMENT_RECORDS="+str(c[8]),
      "M37450_LICENSE_ENTITLEMENTS="+str(c[9]),
      "M37450_ACTIVE_ENTITLEMENT_ROWS="+str(c[10]),
      "M37450_CURRENT_ACTIVE_TENANT_ENTITLEMENTS="+str(c[11]),
      "M37450_LICENSE_EVIDENCE="+state,
      "M37450_LICENSE_RLS_FORCE=3_TABLES",
      "M37450_APP_CAN_READ_ENTITLEMENT=YES",
      "M37450_APP_AUTH_CANNOT_ACTIVATE_LICENSE=PASS",
      "M37450_CYCLE_CONTRIBUTION_PIX_LEDGER=ZERO",
      "M37450_PROVIDER_PAID_STATUS=NOT_ATTESTED",
      "M37450_PRODUCTION_RELEASE=BLOCKED",
      "M37450_REAL_USER_ACTIVATION=OFF",
      "M37450_PIX_REAL=OFF",
      "M37450_NEW_DATABASE=NO",
      "M37450_DB_WRITES=NONE",
    )
