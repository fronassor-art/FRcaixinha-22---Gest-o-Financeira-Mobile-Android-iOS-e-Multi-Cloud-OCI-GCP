#!/usr/bin/env python3
"""M40924: SQL Master writes require an independent, single-use approval digest.

GitHub Actions PostgreSQL 18 disposable ONLY. No HTTP integration, no issuer,
no production grant/migration. Explicitly limited against owner/superuser
compromise, approval theft, or unauthorized approval issuance.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import os
import secrets
import sys

DRAFT_RAW = (
    "m40920.create_draft(text,character varying,character varying,uuid,"
    "numeric,text,text,timestamp with time zone,timestamp with time zone,text)"
)
TRANSITION_RAW = "m40920.transition(text,uuid,integer,text,text)"
DRAFT_GATED = (
    "m40924.gated_draft(text,text,character varying,character varying,uuid,"
    "numeric,text,text,timestamp with time zone,timestamp with time zone,text)"
)
TRANSITION_GATED = "m40924.gated_transition(text,text,uuid,integer,text,text)"
DRAFT_DIGEST = (
    "m40924.draft_digest(character varying,character varying,uuid,numeric,"
    "text,text,timestamp with time zone,timestamp with time zone,text)"
)
TRANSITION_DIGEST = "m40924.transition_digest(uuid,integer,text,text)"

def require_disposable() -> None:
    from m40923_offdb_master_sql_issuer_disposable import require_disposable as prior
    prior()
    if os.environ.get("CI_M40924_DISPOSABLE")!="1":
        raise RuntimeError("M40924_CI_POSTGRES18_DISPOSABLE_ONLY")

def install_gate(conn) -> None:
    conn.execute("CREATE ROLE m40924_approval_owner NOLOGIN NOINHERIT NOBYPASSRLS")
    conn.execute("CREATE ROLE m40924_gate_owner NOLOGIN NOINHERIT NOBYPASSRLS")
    conn.execute("CREATE SCHEMA m40924 AUTHORIZATION m40924_approval_owner")
    conn.execute("REVOKE ALL ON SCHEMA m40924 FROM PUBLIC")
    conn.execute(
        "GRANT USAGE ON SCHEMA m40924 TO m40924_gate_owner,frcaixinha_app_role"
    )
    conn.execute(
        "GRANT USAGE ON SCHEMA m40910,m40920 TO m40924_gate_owner"
    )
    conn.execute(
        "GRANT SELECT ON m40910.sessions,"
        "public.m40560_ci_master_allowlist TO m40924_gate_owner"
    )
    conn.execute("""
        CREATE TABLE m40924.approvals(
            approval_digest text PRIMARY KEY CHECK (
                approval_digest ~ '^[0-9a-f]{64}$'),
            session_digest text NOT NULL CHECK (
                session_digest ~ '^[0-9a-f]{64}$'),
            actor_id uuid NOT NULL,
            tenant_id uuid NOT NULL,
            operation text NOT NULL CHECK (
                operation IN ('DRAFT','PUBLISH','CANCEL')),
            campaign_id uuid,
            expected_revision integer NOT NULL CHECK (
                expected_revision>=0),
            body_digest text NOT NULL CHECK (
                body_digest ~ '^[0-9a-f]{64}$'),
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz
        )
    """)
    conn.execute("ALTER TABLE m40924.approvals OWNER TO m40924_approval_owner")
    conn.execute(
        "REVOKE ALL ON m40924.approvals FROM PUBLIC,frcaixinha_app_role,"
        "m40910_broker_owner,m40921_writer_owner,m40922_session_owner"
    )
    conn.execute(
        "GRANT SELECT,UPDATE(consumed_at) "
        "ON m40924.approvals TO m40924_gate_owner"
    )
    conn.execute("ALTER TABLE m40924.approvals ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE m40924.approvals FORCE ROW LEVEL SECURITY")
    conn.execute(
        "CREATE POLICY m40924_gate_lookup ON m40924.approvals "
        "FOR SELECT TO m40924_gate_owner USING (true)"
    )
    conn.execute(
        "CREATE POLICY m40924_gate_consume ON m40924.approvals "
        "FOR UPDATE TO m40924_gate_owner USING (true) WITH CHECK (true)"
    )
    # M40923's bypass is closed in this disposable DB: no direct old writer.
    for fn in (DRAFT_RAW,TRANSITION_RAW):
        conn.execute("REVOKE ALL ON FUNCTION "+fn
                     +" FROM PUBLIC,frcaixinha_app_role")
        conn.execute("GRANT EXECUTE ON FUNCTION "+fn+" TO m40924_gate_owner")

    # Canonical SQL argument fingerprints: calculated from real function
    # parameters, never accepted as an unverified digest from an app caller.
    conn.execute("""
        CREATE FUNCTION m40924.draft_digest(
          p_tier varchar,p_period varchar,p_version uuid,p_price numeric,
          p_title text,p_benefit text,p_start timestamptz,p_end timestamptz,
          p_reason text)
        RETURNS text LANGUAGE sql IMMUTABLE
        SET search_path=pg_catalog,pg_temp
        AS $body$
          SELECT pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                p_tier,p_period,p_version::text,p_price::text,
                p_title,p_benefit,
                pg_catalog.extract(epoch FROM p_start)::text,
                pg_catalog.extract(epoch FROM p_end)::text,p_reason
            )::text,'UTF8')),'hex')
        $body$
    """)
    conn.execute("""
        CREATE FUNCTION m40924.transition_digest(
          p_campaign uuid,p_expected integer,p_action text,p_reason text)
        RETURNS text LANGUAGE sql IMMUTABLE
        SET search_path=pg_catalog,pg_temp
        AS $body$
          SELECT pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                p_campaign::text,p_expected,p_action,p_reason
            )::text,'UTF8')),'hex')
        $body$
    """)
    for fn in (DRAFT_DIGEST,TRANSITION_DIGEST):
        conn.execute("ALTER FUNCTION "+fn+" OWNER TO m40924_gate_owner")
        conn.execute("REVOKE ALL ON FUNCTION "+fn+" FROM PUBLIC")

    # Wrapper owns exactly SELECT(session), SELECT/UPDATE(consumed_at) approval,
    # and EXECUTE(original legacy writer). Existing writer is no longer app-
    # callable. Approval digest consumption and campaign/audit write share a
    # single SQL transaction; failed append must roll back consumption.
    conn.execute("""
        CREATE FUNCTION m40924.gated_draft(
          p_approval text,p_token text,p_tier varchar,p_period varchar,
          p_version uuid,p_price numeric,p_title text,p_benefit text,
          p_start timestamptz,p_end timestamptz,p_reason text)
        RETURNS TABLE(campaign_id uuid,revision integer,state text)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE
          v_session_digest text;
          v_approval_digest text;
          v_actor uuid;
          v_tenant uuid;
        BEGIN
          IF p_token IS NULL OR pg_catalog.length(p_token) NOT BETWEEN 32 AND 256
            OR p_approval IS NULL
            OR pg_catalog.length(p_approval) NOT BETWEEN 32 AND 256
          THEN
            RAISE EXCEPTION 'M40924_APPROVAL_REQUIRED' USING ERRCODE='42501';
          END IF;
          v_session_digest:=pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8')),'hex');
          v_approval_digest:=pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(p_approval,'UTF8')),'hex');
          SELECT s.user_id,s.tenant_id INTO v_actor,v_tenant
          FROM m40910.sessions AS s
          JOIN public.m40560_ci_master_allowlist AS m ON m.user_id=s.user_id
          WHERE s.token_digest=v_session_digest
            AND s.active_role='MASTER'
            AND s.revoked_at IS NULL
            AND s.expires_at>pg_catalog.clock_timestamp();
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40924_MASTER_SESSION_DENIED' USING ERRCODE='42501';
          END IF;
          UPDATE m40924.approvals AS a
          SET consumed_at=pg_catalog.clock_timestamp()
          WHERE a.approval_digest=v_approval_digest
            AND a.session_digest=v_session_digest
            AND a.actor_id=v_actor
            AND a.tenant_id=v_tenant
            AND a.operation='DRAFT'
            AND a.campaign_id IS NULL
            AND a.expected_revision=0
            AND a.body_digest=m40924.draft_digest(
                p_tier,p_period,p_version,p_price,p_title,p_benefit,
                p_start,p_end,p_reason)
            AND a.expires_at>pg_catalog.clock_timestamp()
            AND a.consumed_at IS NULL;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40924_APPROVAL_DENIED' USING ERRCODE='42501';
          END IF;
          RETURN QUERY
          SELECT r.campaign_id,r.revision,r.state
          FROM m40920.create_draft(
            p_token,p_tier,p_period,p_version,p_price,p_title,p_benefit,
            p_start,p_end,p_reason) AS r;
        END
        $body$
    """)
    conn.execute("""
        CREATE FUNCTION m40924.gated_transition(
          p_approval text,p_token text,p_campaign uuid,p_expected integer,
          p_action text,p_reason text)
        RETURNS TABLE(campaign_id uuid,revision integer,state text)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE
          v_session_digest text;
          v_approval_digest text;
          v_actor uuid;
          v_tenant uuid;
        BEGIN
          IF p_token IS NULL OR pg_catalog.length(p_token) NOT BETWEEN 32 AND 256
            OR p_approval IS NULL
            OR pg_catalog.length(p_approval) NOT BETWEEN 32 AND 256
            OR p_action NOT IN ('PUBLISH','CANCEL')
          THEN
            RAISE EXCEPTION 'M40924_APPROVAL_REQUIRED' USING ERRCODE='42501';
          END IF;
          v_session_digest:=pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8')),'hex');
          v_approval_digest:=pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(p_approval,'UTF8')),'hex');
          SELECT s.user_id,s.tenant_id INTO v_actor,v_tenant
          FROM m40910.sessions AS s
          JOIN public.m40560_ci_master_allowlist AS m ON m.user_id=s.user_id
          WHERE s.token_digest=v_session_digest
            AND s.active_role='MASTER'
            AND s.revoked_at IS NULL
            AND s.expires_at>pg_catalog.clock_timestamp();
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40924_MASTER_SESSION_DENIED' USING ERRCODE='42501';
          END IF;
          UPDATE m40924.approvals AS a
          SET consumed_at=pg_catalog.clock_timestamp()
          WHERE a.approval_digest=v_approval_digest
            AND a.session_digest=v_session_digest
            AND a.actor_id=v_actor
            AND a.tenant_id=v_tenant
            AND a.operation=p_action
            AND a.campaign_id=p_campaign
            AND a.expected_revision=p_expected
            AND a.body_digest=m40924.transition_digest(
                p_campaign,p_expected,p_action,p_reason)
            AND a.expires_at>pg_catalog.clock_timestamp()
            AND a.consumed_at IS NULL;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40924_APPROVAL_DENIED' USING ERRCODE='42501';
          END IF;
          RETURN QUERY
          SELECT r.campaign_id,r.revision,r.state
          FROM m40920.transition(
            p_token,p_campaign,p_expected,p_action,p_reason) AS r;
        END
        $body$
    """)
    for fn in (DRAFT_GATED,TRANSITION_GATED):
        conn.execute("ALTER FUNCTION "+fn+" OWNER TO m40924_gate_owner")
        conn.execute("REVOKE ALL ON FUNCTION "+fn+" FROM PUBLIC")
        conn.execute("GRANT EXECUTE ON FUNCTION "+fn+" TO frcaixinha_app_role")

    # Catalog-proof least privileges in the actual disposable DB.
    for fn in (DRAFT_RAW,TRANSITION_RAW):
        assert not conn.execute(
            "SELECT has_function_privilege('frcaixinha_app_role',%s,'EXECUTE')",
            (fn,),
        ).fetchone()[0],fn
        assert conn.execute(
            "SELECT has_function_privilege('m40924_gate_owner',%s,'EXECUTE')",
            (fn,),
        ).fetchone()[0],fn
    for fn in (DRAFT_GATED,TRANSITION_GATED):
        assert conn.execute(
            "SELECT has_function_privilege('frcaixinha_app_role',%s,'EXECUTE')",
            (fn,),
        ).fetchone()[0],fn
    for role in ("frcaixinha_app_role","m40921_writer_owner",
                 "m40910_broker_owner","m40922_session_owner"):
        for verb in ("SELECT","INSERT","UPDATE","DELETE"):
            assert not conn.execute(
                "SELECT has_table_privilege(%s,'m40924.approvals',%s)",
                (role,verb),
            ).fetchone()[0],(role,verb)
        assert not conn.execute(
            "SELECT pg_catalog.pg_has_role(%s,'m40924_approval_owner','MEMBER')",
            (role,),
        ).fetchone()[0],role
    for field in ("approval_digest","session_digest","actor_id","tenant_id",
                  "operation","campaign_id","expected_revision",
                  "body_digest","expires_at"):
        assert not conn.execute(
            "SELECT has_column_privilege('m40924_gate_owner',"
            "'m40924.approvals',%s,'UPDATE')",(field,),
        ).fetchone()[0],field
    assert conn.execute(
        "SELECT has_column_privilege('m40924_gate_owner',"
        "'m40924.approvals','consumed_at','UPDATE')"
    ).fetchone()[0]
    assert conn.execute(
        "SELECT relrowsecurity,relforcerowsecurity FROM pg_catalog.pg_class "
        "WHERE oid='m40924.approvals'::pg_catalog.regclass"
    ).fetchone()==(True,True)
    print("M40924_LEGACY_SQL_WRITER_APP_EXECUTE=REVOKED")
    print("M40924_APPROVAL_TABLE_APP_ACCESS=ZERO")
    print("M40924_GATE_OWNER_UPDATE_ONLY_CONSUMED_AT=PASS")
    print("M40924_APPROVAL_ROW_LEVEL_SECURITY=FORCED")

def proof(conn) -> None:
    import psycopg
    from psycopg.conninfo import make_conninfo
    from m40900_sql113_acl_fence_disposable import run as fence
    from m40920_master_token_writes_disposable import install_broker
    from m40921_saas_broker_role_split_disposable import split_broker_roles
    from m40922_saas_session_owner_disposable import separate_session_custody
    fence(conn)
    install_broker(conn)
    split_broker_roles(conn)
    separate_session_custody(conn)
    install_gate(conn)

    master=conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist LIMIT 1"
    ).fetchone()[0]
    tenant=conn.execute(
        "SELECT id FROM public.tenants WHERE admin_user_id=%s LIMIT 1",
        (master,),
    ).fetchone()[0]
    version=conn.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()[0]
    token=secrets.token_urlsafe(48)
    member=secrets.token_urlsafe(48)
    now=datetime.now(timezone.utc)
    for t,role in ((token,"MASTER"),(member,"TENANT_MEMBER")):
        conn.execute(
            "INSERT INTO m40910.sessions "
            "(token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
            " VALUES (%s,%s,%s,%s,%s,NULL)",
            (sha256(t.encode()).hexdigest(),master,role,tenant,
             now+timedelta(minutes=30)),
        )
    dsn=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    start=now-timedelta(minutes=1)
    end=now+timedelta(days=6)
    draft_args=(
        token,"ESSENCIAL","MONTHLY",version,Decimal("68.42"),
        "Oferta apenas de teste","Beneficio sintetico sem transferencia real",
        start,end,"Autorizacao separada de sessao e campanha",
    )
    raw_draft_sql="SELECT * FROM m40920.create_draft(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    gate_draft_sql="SELECT * FROM m40924.gated_draft(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    raw_trans_sql="SELECT * FROM m40920.transition(%s,%s,%s,%s,%s)"
    gate_trans_sql="SELECT * FROM m40924.gated_transition(%s,%s,%s,%s,%s,%s)"

    def issue(args,op,*,actor=master,ten=tenant,session=token,
              expires=None,campaign=None,revision=0):
        capability=secrets.token_urlsafe(48)
        fingerprint=conn.execute(
            ("SELECT m40924.draft_digest(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
             if op=="DRAFT" else
             "SELECT m40924.transition_digest(%s,%s,%s,%s)"),
            (args[1:] if op=="DRAFT" else args[1:]),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO m40924.approvals "
            "(approval_digest,session_digest,actor_id,tenant_id,operation,"
            "campaign_id,expected_revision,body_digest,expires_at)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (sha256(capability.encode()).hexdigest(),
             sha256(session.encode()).hexdigest(),actor,ten,op,
             campaign,revision,fingerprint,
             expires or now+timedelta(minutes=1)),
        )
        return capability

    def deny(app,sql,args,label,expected="42501"):
        try:
            with app.transaction():
                app.execute(sql,args)
        except psycopg.Error as exc:
            assert exc.sqlstate==expected,(label,exc.sqlstate)
        else:
            raise AssertionError("M40924_DENIAL_FAILED_"+label)

    with psycopg.connect(dsn,autocommit=True) as app:
        app.execute("SET ROLE frcaixinha_app_role")
        for name,sql,args in (
            ("DIRECT_LEGACY_DRAFT",raw_draft_sql,draft_args),
            ("DIRECT_LEGACY_TRANSITION",raw_trans_sql,
             (token,None,1,"PUBLISH","Motivo sintetico suficiente")),
            ("APP_APPROVAL_READ","SELECT * FROM m40924.approvals",()),
            ("APP_APPROVAL_INSERT",
             "INSERT INTO m40924.approvals DEFAULT VALUES",()),
            ("APP_APPROVAL_CONSUME",
             "UPDATE m40924.approvals SET consumed_at=now()",()),
            ("APP_ASSUME_GATE","SET ROLE m40924_gate_owner",()),
            ("APP_ASSUME_APPROVER","SET ROLE m40924_approval_owner",()),
        ):
            deny(app,sql,args,name)
        app.execute("SELECT set_config('app.current_role','MASTER',false)")
        app.execute(
            "SELECT set_config('app.current_user_id',%s,false)",(str(master),)
        )
        deny(app,gate_draft_sql,("not-an-approval",*draft_args),
             "STOLEN_APP_SQL_PLUS_BEARER_WITHOUT_CAPABILITY")
        denied_member_args=(member,*draft_args[1:])
        denied_member_approval=issue(denied_member_args,"DRAFT",
                                     session=member)
        deny(app,gate_draft_sql,
             (denied_member_approval,*denied_member_args),
             "MEMBER_WITH_FORGED_MASTER_GUC")

        valid=issue(draft_args,"DRAFT")
        changed=list(draft_args)
        changed[4]=Decimal("68.43")
        deny(app,gate_draft_sql,(valid,*changed),"PAYLOAD_TAMPERING")
        deny(app,gate_draft_sql,("totally-wrong-approval",*draft_args),
             "WRONG_APPROVAL")
        assert conn.execute(
            "SELECT consumed_at FROM m40924.approvals "
            "WHERE approval_digest=%s",
            (sha256(valid.encode()).hexdigest(),)
        ).fetchone()==(None,)
        draft=app.execute(gate_draft_sql,(valid,*draft_args)).fetchone()
        assert draft[1:]==(1,"DRAFT")
        deny(app,gate_draft_sql,(valid,*draft_args),"DRAFT_REPLAY")

        trans_args=(
            token,draft[0],1,"PUBLISH",
            "Motivo sintetico suficiente para publicacao",
        )
        publish=issue(trans_args,"PUBLISH",
                      campaign=draft[0],revision=1)
        tampered=(*trans_args[:-1],"Motivo alterado sem nova assinatura valida")
        deny(app,gate_trans_sql,(publish,*tampered),"TRANSITION_TAMPER")
        assert app.execute(
            gate_trans_sql,(publish,*trans_args)
        ).fetchone()==(draft[0],2,"PUBLISHED")
        deny(app,gate_trans_sql,(publish,*trans_args),"PUBLISH_REPLAY")
        cancel_args=(
            token,draft[0],2,"CANCEL",
            "Cancelamento de homologacao em banco sintetico",
        )
        cancel=issue(cancel_args,"CANCEL",campaign=draft[0],revision=2)
        assert app.execute(
            gate_trans_sql,(cancel,*cancel_args)
        ).fetchone()==(draft[0],3,"CANCELED")
        deny(app,gate_trans_sql,(cancel,*cancel_args),"CANCEL_REPLAY")
        print("M40924_MASTER_DRAFT_PUBLISH_CANCEL_GATED=PASS")
        print("M40924_REPLAY_PAYLOAD_TAMPERING_FORGED_GUC=DENIED")

        # Consent cannot be consumed if the append-only audit write fails.
        audit_approval=issue(draft_args,"DRAFT")
        conn.execute(
            "ALTER TABLE m40920.audit ADD CONSTRAINT m40924_fail_audit "
            "CHECK (false) NOT VALID"
        )
        deny(app,gate_draft_sql,(audit_approval,*draft_args),
             "AUDIT_FAILURE_ROLLBACK","23514")
        assert conn.execute(
            "SELECT consumed_at FROM m40924.approvals "
            "WHERE approval_digest=%s",
            (sha256(audit_approval.encode()).hexdigest(),)
        ).fetchone()==(None,)
        conn.execute("ALTER TABLE m40920.audit DROP CONSTRAINT m40924_fail_audit")
        assert app.execute(
            gate_draft_sql,(audit_approval,*draft_args)
        ).fetchone()[1:]==(1,"DRAFT")
        print("M40924_AUDIT_FAILURE_ROLLS_BACK_APPROVAL=PASS")

        expired=issue(draft_args,"DRAFT",
                      expires=now-timedelta(seconds=1))
        deny(app,gate_draft_sql,(expired,*draft_args),
             "EXPIRED_APPROVAL")
        def worker(capability):
            try:
                with psycopg.connect(dsn,autocommit=True) as session:
                    session.execute("SET ROLE frcaixinha_app_role")
                    session.execute(gate_draft_sql,
                                    (capability,*draft_args)).fetchone()
                    return "OK"
            except psycopg.Error as exc:
                return "DENIED_"+str(exc.sqlstate)
        concurrent=issue(draft_args,"DRAFT")
        with ThreadPoolExecutor(max_workers=6) as pool:
            verdicts=list(pool.map(worker,[concurrent]*6))
        assert verdicts.count("OK")==1,verdicts
        assert verdicts.count("DENIED_42501")==5,verdicts
        print("M40924_CONCURRENT_APPROVAL_ONE_OF_SIX=PASS")

        revoked=issue(draft_args,"DRAFT")
        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",(sha256(token.encode()).hexdigest(),)
        )
        deny(app,gate_draft_sql,(revoked,*draft_args),
             "REVOKED_MASTER_WITH_VALID_CAPABILITY")
        assert conn.execute(
            "SELECT consumed_at FROM m40924.approvals "
            "WHERE approval_digest=%s",
            (sha256(revoked.encode()).hexdigest(),)
        ).fetchone()==(None,)
        print("M40924_SESSION_REVOKED_APPROVAL_DENIED=PASS")

    assert conn.execute(
        "SELECT action,revision FROM m40920.audit "
        "WHERE campaign_id=%s ORDER BY revision",
        (draft[0],)
    ).fetchall()==[("DRAFT",1),("PUBLISHED",2),("CANCELED",3)]
    print("M40924_STOLEN_SQL_PLUS_MASTER_BEARER_WITHOUT_APPROVAL=DENIED")
    print("M40924_CAPABILITY_HASH_ONLY_IN_SQL=PASS_SYNTHETIC")
    print("M40924_REAL_OFFDB_APPROVER_OR_ED25519_LINK=NOT_INTEGRATED_NO_GO")
    print("M40924_STOLEN_APPROVAL_OR_PRIVILEGED_DB_OWNER=NOT_MITIGATED_NO_GO")

def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            proof(conn)
    except Exception as exc:
        import traceback
        frame=traceback.extract_tb(exc.__traceback__)[-1]
        print("M40924_FAILURE_SITE="+frame.name+":"+str(frame.lineno))
        if getattr(exc,"sqlstate",None):
            print("M40924_SQLSTATE="+exc.sqlstate)
        print("M40924_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40924_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40924_ORIGINAL_ACL_CHANGES=NONE")
        print("M40924_MIGRATIONS=NONE")
        print("M40924_LOCAL_DB_WRITES=NONE")
        print("M40924_SERVICE_RESTARTS=NONE")
        print("M40924_PIX_REAL=OFF")
        print("M40924_PAGAMENTOS_REAIS=OFF")
        print("M40924_ATIVACAO_REAL=OFF")
        print("M40924_PRODUCTION=BLOCKED")
    print("M40924_STATUS=PASS_DISPOSABLE_SQL_APPROVAL_FENCE_ONLY")
    return 0

if __name__=="__main__":
    sys.exit(main())
