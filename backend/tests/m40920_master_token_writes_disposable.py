#!/usr/bin/env python3
"""M40920: MASTER SaaS writes protected by token, disposable PG18 only.

This isolated proof is NOT a migration, endpoint integration, or production
identity issuer. The existing app role has no direct SQL113 write grants.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import os
import secrets
import sys
from uuid import uuid4


def require_disposable() -> None:
    from m40910_saas_token_gateway_disposable import require_disposable as prior_gate
    prior_gate()
    if os.environ.get("CI_M40920_DISPOSABLE") != "1":
        raise RuntimeError("M40920_GITHUB_PG18_DISPOSABLE_ONLY")


def install_broker(conn) -> None:
    from m40910_saas_token_gateway_disposable import create_broker
    create_broker(conn)
    conn.execute("CREATE SCHEMA m40920 AUTHORIZATION m40910_broker_owner")
    conn.execute("REVOKE ALL ON SCHEMA m40920 FROM PUBLIC")
    conn.execute("GRANT USAGE ON SCHEMA m40920 TO frcaixinha_app_role")
    conn.execute("GRANT USAGE ON SCHEMA public TO m40910_broker_owner")
    conn.execute("""
        CREATE TABLE m40920.audit(
            campaign_id uuid NOT NULL,
            revision integer NOT NULL,
            actor_id uuid NOT NULL,
            action text NOT NULL,
            reason text NOT NULL,
            logged_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            PRIMARY KEY (campaign_id, revision)
        )
    """)
    conn.execute("ALTER TABLE m40920.audit OWNER TO m40910_broker_owner")
    conn.execute("REVOKE ALL ON m40920.audit FROM PUBLIC,frcaixinha_app_role")
    conn.execute(
        "GRANT SELECT ON public.m40560_ci_master_allowlist, "
        "public.platform_license_plans, public.platform_license_price_versions "
        "TO m40910_broker_owner"
    )
    conn.execute("""
        GRANT INSERT(campaign_id,revision,plan_tier,billing_period,
            base_price_version_id,promotional_price,audience,title,
            benefit_description,starts_at,ends_at,state,reason,created_by)
        ON public.platform_saas_promotion_revisions TO m40910_broker_owner
    """)
    conn.execute("""
        CREATE POLICY m40920_broker_append
        ON public.platform_saas_promotion_revisions FOR INSERT
        TO m40910_broker_owner WITH CHECK (true)
    """)
    conn.execute("""
        CREATE FUNCTION m40920.create_draft(
          p_token text, p_tier varchar, p_period varchar,
          p_version uuid, p_price numeric, p_title text, p_benefit text,
          p_start timestamptz, p_end timestamptz, p_reason text)
        RETURNS TABLE(campaign_id uuid, revision integer, state text)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE
          actor uuid;
          current_version uuid;
          new_campaign uuid;
        BEGIN
          IF p_token IS NULL OR pg_catalog.length(p_token) NOT BETWEEN 32 AND 256
          THEN
            RAISE EXCEPTION 'M40920_DENIED_MASTER_SESSION' USING ERRCODE='42501';
          END IF;
          SELECT s.user_id INTO actor FROM m40910.sessions s
          JOIN public.m40560_ci_master_allowlist m ON m.user_id=s.user_id
          WHERE s.token_digest=pg_catalog.encode(
                pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8')),'hex')
            AND s.active_role='MASTER'
            AND s.expires_at>pg_catalog.clock_timestamp()
            AND s.revoked_at IS NULL;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40920_DENIED_MASTER_SESSION' USING ERRCODE='42501';
          END IF;
          IF p_tier NOT IN ('ESSENCIAL','INTERMEDIARIO')
            OR p_period NOT IN ('MONTHLY','ANNUAL')
            OR p_price IS NULL OR p_price<=0 OR p_price>999999.99
            OR p_price<>pg_catalog.round(p_price,2)
            OR p_start IS NULL OR p_end IS NULL
            OR p_start>=p_end OR p_end<=pg_catalog.clock_timestamp()
            OR p_title IS NULL
            OR pg_catalog.length(pg_catalog.btrim(p_title)) NOT BETWEEN 5 AND 120
            OR p_benefit IS NULL
            OR pg_catalog.length(pg_catalog.btrim(p_benefit)) NOT BETWEEN 10 AND 500
            OR p_reason IS NULL
            OR pg_catalog.length(pg_catalog.btrim(p_reason)) NOT BETWEEN 15 AND 500
          THEN
            RAISE EXCEPTION 'M40920_DRAFT_VALIDATION_FAILED' USING ERRCODE='22023';
          END IF;
          PERFORM 1 FROM public.platform_license_plans lp
            WHERE lp.tier=p_tier AND lp.status='ACTIVE';
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40920_INACTIVE_PLAN' USING ERRCODE='22023';
          END IF;
          SELECT v.id INTO current_version
            FROM public.platform_license_price_versions v
            WHERE v.plan_tier=p_tier
            ORDER BY v.created_at DESC,v.id DESC LIMIT 1;
          IF current_version IS DISTINCT FROM p_version THEN
            RAISE EXCEPTION 'M40920_STALE_PRICE_VERSION' USING ERRCODE='22023';
          END IF;
          new_campaign:=pg_catalog.gen_random_uuid();
          INSERT INTO public.platform_saas_promotion_revisions AS r
            (campaign_id,revision,plan_tier,billing_period,base_price_version_id,
            promotional_price,audience,title,benefit_description,starts_at,
            ends_at,state,reason,created_by)
          VALUES (new_campaign,1,p_tier,p_period,p_version,p_price,
            'NEW_ADMIN_ONLY',pg_catalog.btrim(p_title),
            pg_catalog.btrim(p_benefit),p_start,p_end,'DRAFT',
            pg_catalog.btrim(p_reason),actor)
          RETURNING r.campaign_id,r.revision,r.state
          INTO campaign_id,revision,state;
          INSERT INTO m40920.audit(campaign_id,revision,actor_id,action,reason)
          VALUES (campaign_id,revision,actor,'DRAFT',pg_catalog.btrim(p_reason));
          RETURN NEXT;
        END;
        $body$
    """)
    conn.execute("""
        CREATE FUNCTION m40920.transition(
          p_token text, p_campaign uuid, p_expected integer,
          p_action text, p_reason text)
        RETURNS TABLE(campaign_id uuid, revision integer, state text)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE actor uuid; prior public.platform_saas_promotion_revisions%ROWTYPE;
        target text;
        BEGIN
          IF p_token IS NULL OR pg_catalog.length(p_token) NOT BETWEEN 32 AND 256
          THEN
            RAISE EXCEPTION 'M40920_DENIED_MASTER_SESSION' USING ERRCODE='42501';
          END IF;
          SELECT s.user_id INTO actor FROM m40910.sessions s
          JOIN public.m40560_ci_master_allowlist m ON m.user_id=s.user_id
          WHERE s.token_digest=pg_catalog.encode(
                pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8')),'hex')
            AND s.active_role='MASTER'
            AND s.expires_at>pg_catalog.clock_timestamp()
            AND s.revoked_at IS NULL;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40920_DENIED_MASTER_SESSION' USING ERRCODE='42501';
          END IF;
          IF p_campaign IS NULL OR p_expected IS NULL OR p_expected<1
            OR p_action IS NULL OR p_action NOT IN ('PUBLISH','CANCEL')
            OR p_reason IS NULL
            OR pg_catalog.length(pg_catalog.btrim(p_reason)) NOT BETWEEN 15 AND 500
          THEN
            RAISE EXCEPTION 'M40920_TRANSITION_VALIDATION_FAILED'
              USING ERRCODE='22023';
          END IF;
          PERFORM pg_catalog.pg_advisory_xact_lock(
            39067,pg_catalog.hashtext(p_campaign::text));
          SELECT v.* INTO prior
          FROM public.platform_saas_promotion_revisions v
          WHERE v.campaign_id=p_campaign
          ORDER BY v.revision DESC LIMIT 1;
          IF NOT FOUND OR prior.revision<>p_expected THEN
            RAISE EXCEPTION 'M40920_REVISION_CONFLICT' USING ERRCODE='P0001';
          END IF;
          target:=CASE WHEN p_action='PUBLISH' THEN 'PUBLISHED' ELSE 'CANCELED' END;
          IF (target='PUBLISHED' AND prior.state<>'DRAFT')
            OR (target='CANCELED' AND prior.state<>'PUBLISHED')
          THEN
            RAISE EXCEPTION 'M40920_INVALID_TRANSITION' USING ERRCODE='P0001';
          END IF;
          IF target='PUBLISHED' AND prior.ends_at<=pg_catalog.clock_timestamp()
          THEN
            RAISE EXCEPTION 'M40920_EXPIRED_CAMPAIGN' USING ERRCODE='P0001';
          END IF;
          INSERT INTO public.platform_saas_promotion_revisions AS r
            (campaign_id,revision,plan_tier,billing_period,base_price_version_id,
            promotional_price,audience,title,benefit_description,starts_at,
            ends_at,state,reason,created_by)
          VALUES (prior.campaign_id,prior.revision+1,prior.plan_tier,
            prior.billing_period,prior.base_price_version_id,
            prior.promotional_price,prior.audience,prior.title,
            prior.benefit_description,prior.starts_at,prior.ends_at,
            target,pg_catalog.btrim(p_reason),actor)
          RETURNING r.campaign_id,r.revision,r.state
          INTO campaign_id,revision,state;
          INSERT INTO m40920.audit(campaign_id,revision,actor_id,action,reason)
          VALUES (campaign_id,revision,actor,target,pg_catalog.btrim(p_reason));
          RETURN NEXT;
        END;
        $body$
    """)
    for name in (
        "m40920.create_draft(text,varchar,varchar,uuid,numeric,text,text,timestamptz,timestamptz,text)",
        "m40920.transition(text,uuid,integer,text,text)",
    ):
        conn.execute("ALTER FUNCTION "+name+" OWNER TO m40910_broker_owner")
        conn.execute("REVOKE ALL ON FUNCTION "+name+" FROM PUBLIC")
        conn.execute("GRANT EXECUTE ON FUNCTION "+name+" TO frcaixinha_app_role")


def proof(conn) -> None:
    from m40900_sql113_acl_fence_disposable import run as fence
    fence(conn)
    install_broker(conn)
    master=conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist LIMIT 1"
    ).fetchone()[0]
    outsider=conn.execute(
        "SELECT id FROM public.users WHERE id<>%s LIMIT 1",(master,)
    ).fetchone()[0]
    tenant=conn.execute(
        "SELECT id FROM public.tenants WHERE admin_user_id=%s LIMIT 1",(master,)
    ).fetchone()[0]
    version=conn.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()[0]
    now=datetime.now(timezone.utc)
    tokens={}
    def issue(label,actor,role,expiry=None,revoked=None):
        token=secrets.token_urlsafe(40)
        tokens[label]=token
        conn.execute(
            "INSERT INTO m40910.sessions(token_digest,user_id,active_role,"
            "tenant_id,expires_at,revoked_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (sha256(token.encode()).hexdigest(),actor,role,tenant,
             expiry or now+timedelta(minutes=30),revoked),
        )
    issue("master",master,"MASTER")
    issue("member",master,"TENANT_MEMBER")
    issue("fake",outsider,"MASTER")
    issue("expired",master,"MASTER",expiry=now-timedelta(seconds=1))
    issue("revoked",master,"MASTER",revoked=now)

    import psycopg
    from psycopg.conninfo import make_conninfo
    dsn=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    with psycopg.connect(dsn,autocommit=True) as app:
        app.execute("SET ROLE frcaixinha_app_role")
        def denied(fn,label,allowed=("42501",)):
            try:
                with app.transaction():
                    fn()
            except psycopg.Error as exc:
                if exc.sqlstate not in allowed:
                    raise AssertionError("M40920_WRONG_SQLSTATE_"+label+
                                         "_"+str(exc.sqlstate)) from exc
                print("M40920_DENIED_"+label+"="+str(exc.sqlstate))
            else:
                raise AssertionError("M40920_UNAUTHORIZED_"+label)

        def draft(token=tokens["master"]):
            return app.execute(
                "SELECT * FROM m40920.create_draft("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (token,"ESSENCIAL","MONTHLY",version,Decimal("49.33"),
                 "Oferta de homologacao","Beneficio ficticio para teste isolado",
                 now-timedelta(minutes=1),now+timedelta(days=10),
                 "Justificativa sintetica sem cobranca"),
            ).fetchone()

        def transition(token,campaign,revision,action):
            return app.execute(
                "SELECT * FROM m40920.transition(%s,%s,%s,%s,%s)",
                (token,campaign,revision,action,
                 "Transicao sintetica autorizada em CI"),
            ).fetchone()

        denied(lambda:app.execute(
            "SELECT * FROM public.platform_saas_promotion_revisions"
        ),"DIRECT_PROMOTION_READ")
        denied(lambda:app.execute(
            "INSERT INTO public.platform_saas_promotion_revisions "
            "DEFAULT VALUES"
        ),"DIRECT_PROMOTION_WRITE")
        denied(lambda:app.execute("SELECT * FROM m40920.audit"),"DIRECT_AUDIT")
        denied(lambda:app.execute(
            "INSERT INTO m40910.sessions DEFAULT VALUES"
        ),"DIRECT_SESSION_ISSUANCE")
        denied(lambda:app.execute("SET ROLE m40910_broker_owner"),"ROLE_ESCALATION")
        for label in ("member","fake","expired","revoked"):
            denied(lambda x=label:draft(tokens[x]),label.upper())
        denied(lambda:draft(secrets.token_urlsafe(40)),"UNKNOWN_TOKEN")
        for key,value in (
            ("app.current_role","MASTER"),
            ("app.current_user_id",str(master)),
            ("app.current_tenant_id",str(tenant)),
        ):
            app.execute("SELECT pg_catalog.set_config(%s,%s,false)",(key,value))
        denied(lambda:draft(tokens["member"]),"FORGED_GUC")
        denied(lambda:draft(tokens["fake"]),"FORGED_ALLOWLIST")
        first=draft()
        second=draft()
        assert first[1:]==(1,"DRAFT") and second[1:]==(1,"DRAFT")
        assert first[0]!=second[0]
        assert conn.execute(
            "SELECT count(*) FROM m40920.audit"
        ).fetchone()[0]==2
        print("M40920_MASTER_DRAFT_AND_ATOMIC_AUDIT=PASS")
        denied(lambda:transition(tokens["member"],first[0],1,"PUBLISH"),
               "MEMBER_TRANSITION")
        denied(lambda:transition(tokens["master"],first[0],99,"PUBLISH"),
               "REVISION_MISMATCH",("P0001",))
        before=conn.execute(
            "SELECT count(*) FROM public.platform_saas_promotion_revisions"
        ).fetchone()[0]
        conn.execute(
            "ALTER TABLE m40920.audit ADD CONSTRAINT m40920_ci_fail_audit "
            "CHECK (false) NOT VALID"
        )
        denied(lambda:draft(),"FORCED_AUDIT_FAILURE",("23514",))
        assert conn.execute(
            "SELECT count(*) FROM public.platform_saas_promotion_revisions"
        ).fetchone()[0]==before
        conn.execute("ALTER TABLE m40920.audit DROP CONSTRAINT m40920_ci_fail_audit")
        print("M40920_AUDIT_FAILURE_ROLLS_BACK_DRAFT=PASS")
        assert transition(tokens["master"],first[0],1,"PUBLISH")[1:]==(2,"PUBLISHED")
        denied(lambda:transition(tokens["master"],second[0],1,"PUBLISH"),
               "OVERLAPPING_PUBLISH",("P0001",))
        denied(lambda:transition(tokens["master"],first[0],1,"CANCEL"),
               "STALE_CANCEL",("P0001",))
        assert transition(tokens["master"],first[0],2,"CANCEL")[1:]==(3,"CANCELED")
        assert transition(tokens["master"],second[0],1,"PUBLISH")[1:]==(2,"PUBLISHED")
        denied(lambda:transition(tokens["master"],first[0],3,"PUBLISH"),
               "REPUBLISH_CANCELED",("P0001",))
        count=conn.execute("SELECT count(*) FROM m40920.audit").fetchone()[0]
        assert count==5, count
        assert conn.execute(
            "SELECT count(*) FROM public.platform_saas_promotion_revisions "
            "WHERE campaign_id IN (%s,%s)",(first[0],second[0])
        ).fetchone()[0]==5
        print("M40920_DRAFT_PUBLISH_CANCEL_APPEND_ONLY=PASS")
        print("M40920_CONFLICTS_AND_SNAPSHOT_TRIGGER=PASS")
        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",
            (sha256(tokens["master"].encode()).hexdigest(),),
        )
        denied(lambda:draft(),"LIVE_REVOKE_NEW_DRAFT")
        denied(lambda:transition(tokens["master"],second[0],2,"CANCEL"),
               "LIVE_REVOKE_TRANSITION")
        print("M40920_REVOCATION_AND_GUC_SPOOF=PASS")
        print("M40920_VALID_STOLEN_MASTER_BEARER=NOT_MITIGATED_NO_GO")
        print("M40920_MASTER_LIST_READ=NOT_RESTORED")
        print("M40920_HTTP_AND_REAL_ISSUER=NOT_INTEGRATED")


def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            proof(conn)
    except Exception as exc:
        import traceback
        site=traceback.extract_tb(exc.__traceback__)[-1]
        print("M40920_FAILURE_SITE="+site.name+":"+str(site.lineno))
        print("M40920_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40920_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40920_ORIGINAL_ACL_CHANGES=NONE")
        print("M40920_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40920_MIGRATIONS=NONE")
        print("M40920_LOCAL_DB_WRITES=NONE")
        print("M40920_SERVICE_RESTARTS=NONE")
        print("M40920_PIX_REAL=OFF")
        print("M40920_PAGAMENTOS_REAIS=OFF")
        print("M40920_ATIVACAO_REAL=OFF")
        print("M40920_PRODUCTION=BLOCKED")
    print("M40920_STATUS=PASS_DISPOSABLE_MASTER_WRITES_ONLY")
    return 0


if __name__=="__main__":
    sys.exit(main())
