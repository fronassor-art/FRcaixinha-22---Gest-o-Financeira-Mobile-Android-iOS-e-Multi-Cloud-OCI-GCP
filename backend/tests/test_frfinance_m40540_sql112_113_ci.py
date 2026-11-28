"""M40540 source-only catalog classifier safeguards; no DB connections."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/scripts/frfinance_m40540_sql112_113_catalog_readonly.sql").read_text()
SH=(ROOT/"backend/scripts/frfinance_m40540_sql112_113_catalog_readonly.sh").read_text()
A=(ROOT/"backend/migrations/112_frfinance_master_independent_saas_prices.sql").read_text()
B=(ROOT/"backend/migrations/113_frfinance_saas_new_admin_promotions.sql").read_text()

def test_fixed_original_identity():
    for s in ("BEGIN READ ONLY;","ROLLBACK;","frcaixinha_aistudio_dev",
              "frc_ai_owner","inet_server_port()=5433","transaction_read_only",
              "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"):
        assert s in SQL

def test_sql112_evidence_from_catalog_not_data():
    for s in ("annual_price","attgenerated='s'","attgenerated=''",
              "platform_license_annual_price_positive",
              "PENDING_GENERATED_ANNUAL","STRUCTURE_PRESENT_NOT_PROVENANCE"):
        assert s in SQL
    assert "ALTER COLUMN annual_price DROP EXPRESSION" in A

def test_sql113_evidence_from_catalog_not_data():
    for s in ("platform_saas_promotion_revisions","frfinance_saas_promo_master_select",
              "frfinance_saas_promo_master_insert","frfinance_guard_saas_promo_append",
              "frfinance_saas_new_admin_published_promotions",
              "platform_saas_promotions_latest","platform_saas_promotions_period"):
        assert s in SQL and s in B
    assert "NOT_INSTALLED" in SQL and "PARTIAL_OR_DRIFT" in SQL

def test_sql_readonly_no_application_table_rows():
    cleaned=re.sub(r"(?m)^\s*--.*$","",SQL)
    cleaned=re.sub(r"(?m)^\s*\\(?:echo|set).*$","",cleaned)
    cleaned=re.sub(r"'(?:''|[^'])*'","''",cleaned)
    for regex in (r"\b(?:INSERT|UPDATE|DELETE|TRUNCATE|CREATE|ALTER|DROP|GRANT|REVOKE|COPY)\b",
                  r"\bFROM\s+public\.",r"\bJOIN\s+public\.",
                  r"\\(?:!|copy|gexec|include|i|o)\b"):
        assert re.search(regex,cleaned,flags=re.I) is None
    assert SQL.count(r"\gset")==2

def test_shell_does_not_change_database_or_services():
    for s in ("env -i","default_transaction_read_only=on","-X -W -q -t -A -v ON_ERROR_STOP=1",
              "-h 127.0.0.1 -p 5433","-U frc_ai_owner","-d frcaixinha_aistudio_dev",
              "M38794_PROJECT_SEPARATION=PASS_STATIC","M40540_MIGRATIONS=NONE",
              "M40540_DB_WRITES=NONE","M40540_SERVICE_RESTARTS=NONE",
              "M40540_PRODUCTION=BLOCKED"):
        assert s in SH
    for s in ("PGPASSWORD","api.env","DATABASE_URL","pg_ctl restart","pg_ctl start",
              "pg_ctl stop","psql -c"):
        assert s not in SH

def test_classification_not_installation():
    for s in ("M40540_SQL112=:m40540_sql112","M40540_SQL113=:m40540_sql113",
              "PASS_CLASSIFICATION_ONLY","M40540_AUTOMATIC_REPAIR=OFF"):
        assert s in (SQL+"\n"+SH)
