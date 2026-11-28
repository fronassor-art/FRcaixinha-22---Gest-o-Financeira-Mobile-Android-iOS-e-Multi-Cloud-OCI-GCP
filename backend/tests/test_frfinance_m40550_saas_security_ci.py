"""M40550 offline source guards; no original PostgreSQL connections."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/scripts/frfinance_m40550_saas_security_catalog_readonly.sql").read_text()
SH=(ROOT/"backend/scripts/frfinance_m40550_saas_security_catalog_readonly.sh").read_text()
M112=(ROOT/"backend/migrations/112_frfinance_master_independent_saas_prices.sql").read_text()
M113=(ROOT/"backend/migrations/113_frfinance_saas_new_admin_promotions.sql").read_text()

def test_read_only_original_identity():
    for marker in ("BEGIN READ ONLY;","ROLLBACK;","frcaixinha_aistudio_dev",
                   "frc_ai_owner","inet_server_port()=5433","transaction_read_only",
                   "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"):
        assert marker in SQL

def test_sql112_column_and_history_update_guards():
    for marker in ("platform_license_annual_price_positive","attgenerated=''",
                   "a.attnotnull","annual_price','INSERT'","annual_price','UPDATE'",
                   "M40550_SQL112_NO_HISTORICAL_UPDATE=PASS"):
        assert marker in SQL
    assert "GRANT INSERT (annual_price)" in M112
    assert "REVOKE UPDATE, DELETE, TRUNCATE" in M112

def test_sql113_master_policies_and_rls():
    for marker in ("frfinance_saas_promo_master_select",
                   "frfinance_saas_promo_master_insert","polcmd='r'","polcmd='a'",
                   "polpermissive","relrowsecurity AND relforcerowsecurity",
                   "M40550_SQL113_MASTER_RLS=PASS"):
        assert marker in SQL
    assert M113.count("CREATE POLICY frfinance_saas_promo_master_")==2

def test_sql113_function_privileges_and_safe_search_path():
    for marker in ("has_any_column_privilege","has_function_privilege",
                   "frcaixinha_auth_role","prosecdef","search_path=pg_catalog, pg_temp",
                   "M39067_OVERLAPPING_PUBLISHED_PROMOTION",
                   "M40550_SQL113_FUNCTIONS_SECURITY=PASS"):
        assert marker in SQL
    assert "SECURITY DEFINER SET search_path=pg_catalog,pg_temp" in M113

def test_insert_only_trigger_and_not_executed():
    for marker in ("pg_catalog.pg_trigger","t.tgenabled='O'",
                   "t.tgfoid=pg_catalog.to_regprocedure",
                   "(t.tgtype::int & 4)=4","(t.tgtype::int & 16)=0",
                   "M40550_FUNCTION_EXECUTION=NONE"):
        assert marker in SQL

def test_only_catalog_sql_not_dml_or_application_rows():
    code=re.sub(r"(?m)^\s*--.*$","",SQL)
    code=re.sub(r"(?m)^\s*\\(?:echo|set).*$","",code)
    code=re.sub(r"'(?:''|[^'])*'","''",code)
    for pattern in (r"\b(?:INSERT|UPDATE|DELETE|TRUNCATE|CREATE|ALTER|DROP|GRANT|REVOKE|COPY|CALL)\b",
                    r"\bFROM\s+public\.",r"\bJOIN\s+public\.",
                    r"\bpg_read_file\b",r"\\(?:!|copy|gexec|include|i|setenv|o)\b"):
        assert re.search(pattern,code,flags=re.I) is None, pattern
    assert SQL.count("1 / CASE WHEN")==7

def test_shell_fixed_destination_hidden_password_no_mutations():
    for marker in ("env -i","default_transaction_read_only=on",
                   "M38794_PROJECT_SEPARATION=PASS_STATIC",
                   "-X -W -q -t -A -v ON_ERROR_STOP=1",
                   "-h 127.0.0.1 -p 5433","-U frc_ai_owner",
                   "-d frcaixinha_aistudio_dev","M40550_PRODUCTION=BLOCKED"):
        assert marker in SH
    for forbidden in ("PGPASSWORD","api.env","DATABASE_URL","psql -c",
                      "pg_ctl start","pg_ctl stop","pg_ctl restart"):
        assert forbidden not in SH

def test_operations_off():
    for marker in ("M40550_MIGRATIONS=NONE","M40550_DB_WRITES=NONE",
                   "M40550_SERVICE_RESTARTS=NONE","M40550_PIX_REAL=OFF",
                   "M40550_PAGAMENTOS_REAIS=OFF","M40550_ATIVACAO_REAL=OFF",
                   "M40550_FR_CAIXINHA_2_2=NOT_ACCESSED"):
        assert marker in SH
