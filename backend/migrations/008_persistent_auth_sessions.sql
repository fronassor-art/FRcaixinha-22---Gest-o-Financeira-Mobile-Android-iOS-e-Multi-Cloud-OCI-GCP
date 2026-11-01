-- Sessões de homologação persistentes e segregadas do papel financeiro.
-- O papel de aplicação não recebe acesso a sessões nem a hashes de credenciais.
REVOKE ALL ON public.sessions FROM PUBLIC, frcaixinha_app_role;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions FORCE ROW LEVEL SECURITY;

CREATE POLICY sessions_auth_read ON public.sessions FOR SELECT TO frcaixinha_auth_role USING (true);
CREATE POLICY sessions_auth_insert ON public.sessions FOR INSERT TO frcaixinha_auth_role WITH CHECK (true);
CREATE POLICY sessions_auth_update ON public.sessions FOR UPDATE TO frcaixinha_auth_role USING (true) WITH CHECK (true);

GRANT SELECT (id, token_hash, user_id, active_role, active_tenant_id, expires_at, revoked_at)
    ON public.sessions TO frcaixinha_auth_role;
GRANT INSERT (id, token_hash, user_id, active_role, active_tenant_id, expires_at, ip_address, user_agent)
    ON public.sessions TO frcaixinha_auth_role;
GRANT UPDATE (active_role, active_tenant_id, expires_at, revoked_at)
    ON public.sessions TO frcaixinha_auth_role;
