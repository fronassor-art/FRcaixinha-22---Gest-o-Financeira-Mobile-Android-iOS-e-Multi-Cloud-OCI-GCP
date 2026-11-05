"""Preflight SQL do AI Studio com PostgreSQL 18 DESCARTAVEL do GitHub Actions.

Nunca executa contra o Termux. As senhas de CI sao sintéticas.
Este teste deliberadamente NAO acessa serviços financeiros, Pix ou dados reais.
"""
import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest


def _dsn(env: str) -> str:
    if os.environ.get("AI_STUDIO_CI_PG18") != "1":
        pytest.skip("Executar somente no CI PostgreSQL 18 descartavel")
    value = os.environ[env]
    p = urlparse(value)
    if p.hostname not in {"127.0.0.1", "localhost"} or p.path != "/frcaixinha_ci":
        raise AssertionError("DSN fora do PostgreSQL isolado de CI")
    return value


@pytest.mark.asyncio
async def test_pg18_migrations_master_rls_and_append_only_price():
    admin = await asyncpg.connect(_dsn("CI_ADMIN_DATABASE_URL"))
    application = await asyncpg.connect(_dsn("DATABASE_URL"))
    user_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    member_id = uuid.uuid4()
    try:
        version = await admin.fetchval("SELECT current_setting('server_version_num')::integer")
        assert 180000 <= version < 190000, "Nao e PostgreSQL 18"
        assert await admin.fetchval("SELECT current_database()") == "frcaixinha_ci"
        assert not await application.fetchval(
            "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert await application.fetchval(
            "SELECT count(*) FROM public.platform_license_plans"
        ) == 0, "Catalogo Master deve ser invisivel fora de contexto"
        assert await admin.fetchval(
            "SELECT to_regprocedure('public.auth_active_membership_contexts(text)') IS NOT NULL"
        ), "Acesso único nomeado precisa existir"
        assert await admin.fetchval(
            "SELECT to_regprocedure('public.auth_active_membership_contexts(uuid)') IS NULL"
        ), "A função anterior por UUID não pode continuar exposta"
        assert await admin.fetchval(
            "SELECT has_function_privilege('frcaixinha_auth_role',"
            "'public.auth_active_membership_contexts(text)','EXECUTE')"
        ), "O papel de autenticação deve possuir o acesso mínimo necessário"
        assert await admin.fetchval(
            "SELECT to_regprocedure('public.auth_active_memberships(text)') IS NOT NULL"
        ), "Consulta de vinculos deve exigir token"
        assert await admin.fetchval(
            "SELECT to_regprocedure('public.auth_active_memberships(uuid)') IS NULL"
        ), "Consulta por UUID deve estar removida"
        assert not await application.fetchval(
            "SELECT has_function_privilege(current_user,"
            "'public.auth_active_memberships(text)','EXECUTE')"
        ), "Papel financeiro não consulta vinculos de autenticação"
        assert await admin.fetchval(
            "SELECT pg_get_constraintdef(oid) LIKE '%PENDING_CONTEXT%' "
            "FROM pg_constraint WHERE conrelid='public.sessions'::regclass "
            "AND conname='sessions_active_role_check'"
        ), "O token provisório deve ser validado no esquema"
        assert not await application.fetchval(
            "SELECT has_function_privilege(current_user,"
            "'public.auth_active_membership_contexts(text)','EXECUTE')"
        ), "App financeiro não pode consultar nomes de vínculos via Auth"
        assert not await admin.fetchval(
            "SELECT has_column_privilege('frcaixinha_auth_role',"
            "'public.sessions','expires_at','UPDATE')"
        ), "Auth não pode renovar sessão diretamente"
        assert not await admin.fetchval(
            "SELECT has_column_privilege('frcaixinha_auth_role',"
            "'public.sessions','revoked_at','UPDATE')"
        ), "Auth não pode revogar sessão diretamente"
        assert await admin.fetchval(
            "SELECT has_function_privilege('frcaixinha_auth_role',"
            "'public.auth_refresh_session(text)','EXECUTE')"
        ), "Auth deve renovar apenas pela função de sessão"
        assert await admin.fetchval(
            "SELECT has_function_privilege('frcaixinha_auth_role',"
            "'public.auth_revoke_owned_session(text,uuid)','EXECUTE')"
        ), "Auth deve revogar sessão própria pela função vinculada a token"
        assert not await application.fetchval(
            "SELECT has_function_privilege(current_user,"
            "'public.auth_revoke_all_sessions(text)','EXECUTE')"
        ), "O papel financeiro não pode revogar sessões"
        assert await admin.fetchval(
            "SELECT to_regclass('public.auth_login_proofs') IS NOT NULL"
        ), "Provas efemeras de login devem existir"
        assert await admin.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_class WHERE "
            "oid='public.auth_login_rate_limits'::regclass "
            "AND relrowsecurity AND relforcerowsecurity)"
        ), "Limites compartilhados exigem FORCE RLS"
        assert await admin.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='auth_login_proofs' "
            "AND column_name='credential_fingerprint')"
        ), "Provas devem ser vinculadas a credencial verificada"
        for trigger in ('auth_password_changed_revoke', 'auth_password_deleted_revoke'):
            assert await admin.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_trigger "
                "WHERE tgrelid='public.credentials'::regclass "
                "AND tgname=$1 AND NOT tgisinternal)", trigger,
            ), "Rotacao/exclusao devem invalidar sessoes"
        assert not await admin.fetchval(
            "SELECT has_column_privilege('frcaixinha_auth_role',"
            "'public.credentials','password_hash','SELECT')"
        ), "Conta Auth nao deve consultar hashes de senha"
        assert not await admin.fetchval(
            "SELECT has_table_privilege('frcaixinha_auth_role',"
            "'public.sessions','INSERT')"
        ), "Conta Auth nao deve emitir sessao por INSERT direto"
        assert await admin.fetchval(
            "SELECT has_function_privilege('frcaixinha_auth_role',"
            "'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')"
        ), "Emissao depende de prova separada"
        assert await admin.fetchval(
            "SELECT has_column_privilege('frcaixinha_verifier_role',"
            "'public.credentials','password_hash','SELECT')"
        ), "Verificador precisa somente ler credenciais"
        assert not await admin.fetchval(
            "SELECT has_function_privilege('frcaixinha_verifier_role',"
            "'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')"
        ), "Verificador nao deve emitir sessoes"
        assert not await application.fetchval(
            "SELECT has_table_privilege(current_user,'public.sessions','SELECT')"
        ), "Sessões continuam isoladas do app"
        assert not await admin.fetchval(
            "SELECT has_column_privilege('frcaixinha_auth_role',"
            "'public.sessions','active_role','UPDATE')"
        ), "Auth não pode alterar o papel diretamente"
        assert not await admin.fetchval(
            "SELECT has_column_privilege('frcaixinha_auth_role',"
            "'public.sessions','active_tenant_id','UPDATE')"
        ), "Auth não pode alterar o tenant diretamente"
        assert await admin.fetchval(
            "SELECT has_function_privilege('frcaixinha_auth_role',"
            "'public.auth_promote_pending_session(text,varchar,uuid)',"
            "'EXECUTE')"
        ), "Auth deve promover sessão apenas por função controlada"
        assert await admin.fetchval(
            "SELECT has_function_privilege('frcaixinha_auth_role',"
            "'public.auth_switch_session_context(text,varchar,uuid)',"
            "'EXECUTE')"
        ), "Auth deve trocar contexto apenas por função controlada"
        assert not await application.fetchval(
            "SELECT has_function_privilege(current_user,"
            "'public.auth_switch_session_context(text,varchar,uuid)',"
            "'EXECUTE')"
        ), "O papel financeiro nunca pode trocar perfil Auth"
        assert await admin.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_constraint "
            "WHERE conrelid='public.sessions'::regclass "
            "AND conname='sessions_absolute_8h_guard')"
        ), "Sessões precisam de teto absoluto de 8h"
        assert await admin.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_policies "
            "WHERE schemaname='public' AND tablename='sessions' "
            "AND policyname='sessions_auth_insert' AND cmd='INSERT' "
            "AND with_check LIKE '%PENDING_CONTEXT%')"
        ), "O papel Auth só pode inserir sessões provisórias"
        assert await admin.fetchval(
            "SELECT count(*) FROM public.saas_payment_intents"
        ) == 0, "Nenhuma cobrança deve surgir das migrações"
        assert await admin.fetchval(
            "SELECT count(*) FROM public.saas_license_entitlements"
        ) == 0, "Nenhuma licença deve ser ativada pela migração"
        assert await admin.fetchval(
            "SELECT count(*) FROM public.invite_email_verification"
        ) == 0, "Nenhum destinatário validado automaticamente"
        assert not await application.fetchval(
            "SELECT has_table_privilege(current_user,'public.saas_payment_intents','INSERT')"
        ), "Papel app não pode criar cobranças"
        assert not await application.fetchval(
            "SELECT has_table_privilege(current_user,'public.invite_email_verification','SELECT')"
        ), "Papel app não pode ler tokens de convite"
        assert await admin.fetchval(
            "SELECT count(*) FROM public.contract_documents"
        ) == 0, "Sem aceitar termos por inferência"
        assert await admin.fetchval(
            "SELECT count(*) FROM public.saas_subscription_preparations"
        ) == 0, "Nenhuma licença é preparada sem aceite explícito"
        assert not await application.fetchval(
            "SELECT has_table_privilege(current_user,"
            "'public.contract_acceptances','INSERT')"
        ), "API app nunca pode forjar aceite"
        assert not await application.fetchval(
            "SELECT has_table_privilege(current_user,"
            "'public.saas_subscription_preparations','INSERT')"
        ), "API app nunca deve ativar licenciamento"
        assert await application.fetchval(
            "SELECT has_column_privilege(current_user,'public.users','cpf','SELECT')"
        ) is False, "CPF nao pode ser legivel pela aplicacao"
        assert await application.fetchval(
            "SELECT has_column_privilege(current_user,'public.users','email','SELECT')"
        ) is False, "E-mail de autenticacao nao pode ser legivel pela aplicacao"
        assert await application.fetchval(
            "SELECT has_column_privilege(current_user,'public.users','full_name','SELECT')"
        ) is True, "Consultas de nome devem continuar operacionais"
        assert await application.fetchval(
            "SELECT has_table_privilege(current_user,'public.credentials','SELECT')"
        ) is False, "Hash de senhas nao pode ser legivel pela aplicacao"

        await admin.execute(
            "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master) "
            "VALUES($1,$2,$3,$4,$5,TRUE)",
            user_id, f"ci-{user_id}@example.invalid", "Master sintetico CI",
            user_id.hex[:14], "00000000000"
        )
        await admin.execute(
            "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master) "
            "VALUES($1,$2,$3,$4,$5,FALSE)",
            admin_id, f"ci-admin-{admin_id}@example.invalid", "Admin sintetico",
            admin_id.hex[:14], "00000000000"
        )
        await admin.execute(
            "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id)"
            "VALUES($1,'Tenant sintetico CI',$2,$3)", tenant_id, str(uuid.uuid4()), admin_id
        )
        await admin.execute(
            "INSERT INTO public.memberships(id,tenant_id,user_id,role)"
            "VALUES($1,$2,$3,'TENANT_ADMIN')", member_id, tenant_id, admin_id
        )
        await admin.execute(
            "INSERT INTO public.quotas(tenant_id,membership_id,quota_number,value_brl)"
            "VALUES($1,$2,1,150.00)", tenant_id, member_id
        )
        tx = application.transaction()
        await tx.start()
        try:
            await application.execute(
                "SELECT set_config('app.current_user_id',$1,true)", str(user_id)
            )
            await application.execute(
                "SELECT set_config('app.current_role','MASTER',true)"
            )
            await application.execute(
                "SELECT set_config('app.current_tenant_id','',true)"
            )
            assert await application.fetchval("SELECT count(*) FROM public.tenants") == 1
            assert await admin.fetchval("SELECT count(*) FROM public.quotas") == 1
            assert await application.fetchval(
                "SELECT count(*) FROM public.platform_license_plans"
            ) == 3
            assert await application.fetchval(
                "SELECT count(*) FROM public.platform_license_price_versions"
            ) == 2

            new_id = await application.fetchval(
                "INSERT INTO public.platform_license_price_versions"
                "(plan_tier,monthly_price,changed_by,reason)"
                " VALUES('ESSENCIAL',99.90,$1,'Revisao sintetica autorizada de catalogo') "
                "RETURNING id", user_id
            )
            assert new_id is not None
            annual = await application.fetchval(
                "SELECT annual_price FROM public.platform_license_price_versions "
                "WHERE id=$1", new_id
            )
            assert str(annual) == "999.00"
            await application.execute(
                "INSERT INTO public.audit_events"
                "(actor_id,actor_role,action,object_type,object_id,reason,evidence_ref) "
                "VALUES($1,'MASTER','SAAS_PRICE_VERSION_CREATED','LICENSE_PRICE',"
                "$2,'Revisao sintetica autorizada de catalogo','CI_PRE_MIGRATION')",
                user_id, str(new_id)
            )
            assert await application.fetchval(
                "SELECT count(*) FROM public.quotas"
            ) == 0, "O Master nao herda quotas de membros"
        finally:
            await tx.rollback()

        assert await admin.fetchval(
            "SELECT count(*) FROM public.platform_license_price_versions"
        ) == 2, "Rollback deve descartar alteracao sintetica"

        tx = application.transaction()
        await tx.start()
        try:
            await application.execute("SELECT set_config('app.current_user_id',$1,true)",str(user_id))
            await application.execute("SELECT set_config('app.current_role','TENANT_MEMBER',true)")
            assert await application.fetchval(
                "SELECT count(*) FROM public.platform_license_price_versions"
            ) == 0, "Contexto membro nao pode ler precos administrativos"
            with pytest.raises(asyncpg.PostgresError):
                await application.execute(
                    "INSERT INTO public.platform_license_price_versions"
                    "(plan_tier,monthly_price,changed_by,reason)"
                    " VALUES('ESSENCIAL',99.90,$1,'Alteracao indevida de preco por membro')",
                    user_id
                )
        finally:
            await tx.rollback()
    finally:
        await application.close()
        await admin.execute("DELETE FROM public.tenants WHERE id=$1",tenant_id)
        await admin.execute("DELETE FROM public.users WHERE id=ANY($1::uuid[])",[user_id,admin_id])
        await admin.close()
