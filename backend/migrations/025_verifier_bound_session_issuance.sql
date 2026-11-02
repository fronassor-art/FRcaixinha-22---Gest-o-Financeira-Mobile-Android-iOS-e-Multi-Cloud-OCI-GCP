-- AI Studio 025 — separacao entre comprovar senha e emitir sessao.
-- SOMENTE banco descartavel CI; NAO aplicar ao banco local do Termux.
-- A identidade verificadora pode consultar hashes, mas nao criar sessoes.
-- A identidade Auth pode gerenciar sessoes, mas nao consultar hashes nem
-- criar PENDING_CONTEXT arbitrariamente. Emissao requer prova efemera emitida
-- pela segunda identidade apos verificacao de senha no processo FastAPI.
-- Comprometimento TOTAL do backend/ambas as credenciais continua fora do escopo.

DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_verifier_role') THEN
    CREATE ROLE frcaixinha_verifier_role
      NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
END $role$;

GRANT USAGE ON SCHEMA public TO frcaixinha_verifier_role;
GRANT SELECT (id,email,full_name,status,is_master)
  ON public.users TO frcaixinha_verifier_role;
GRANT SELECT (user_id,password_hash)
  ON public.credentials TO frcaixinha_verifier_role;

CREATE POLICY users_verifier_identity_read
  ON public.users FOR SELECT TO frcaixinha_verifier_role USING (true);

REVOKE SELECT (user_id,password_hash)
  ON public.credentials FROM frcaixinha_auth_role;

CREATE TABLE public.auth_login_proofs (
  proof_hash text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  CONSTRAINT login_proof_expiry_guard
    CHECK (expires_at > created_at
       AND expires_at <= created_at + INTERVAL '90 seconds')
);

REVOKE ALL ON public.auth_login_proofs FROM PUBLIC,frcaixinha_app_role,
  frcaixinha_auth_role,frcaixinha_verifier_role;
ALTER TABLE public.auth_login_proofs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_login_proofs FORCE ROW LEVEL SECURITY;
CREATE POLICY auth_proof_verifier_insert
  ON public.auth_login_proofs FOR INSERT TO frcaixinha_verifier_role
  WITH CHECK (
    consumed_at IS NULL
    AND expires_at <= created_at + INTERVAL '90 seconds'
  );
GRANT INSERT (proof_hash,user_id,expires_at)
  ON public.auth_login_proofs TO frcaixinha_verifier_role;

-- A conta Auth não deve conseguir criar sessoes por INSERT direto.
REVOKE INSERT (id,token_hash,user_id,active_role,active_tenant_id,
  expires_at,ip_address,user_agent)
  ON public.sessions FROM frcaixinha_auth_role;

CREATE FUNCTION public.auth_issue_pending_session(
  p_user_id uuid, p_raw_session_token text, p_raw_proof text
)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp
AS $$
DECLARE
  v_hash text;
  v_session_hash text;
  v_actor_active boolean;
BEGIN
  IF p_user_id IS NULL
     OR p_raw_session_token IS NULL
     OR p_raw_proof IS NULL
     OR length(p_raw_session_token) NOT BETWEEN 32 AND 512
     OR length(p_raw_proof) NOT BETWEEN 32 AND 512
  THEN RETURN false; END IF;

  v_hash:=encode(public.digest(p_raw_proof,'sha256'),'hex');
  v_session_hash:=encode(public.digest(p_raw_session_token,'sha256'),'hex');

  -- Tranca prova antes de consumi-la: duas emissoes concorrentes nao passam.
  PERFORM 1 FROM public.auth_login_proofs AS p
  WHERE p.proof_hash=v_hash
    AND p.user_id=p_user_id
    AND p.consumed_at IS NULL
    AND p.expires_at>NOW()
  FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;

  SELECT EXISTS(
    SELECT 1 FROM public.users
    WHERE id=p_user_id AND status='ACTIVE'
  ) INTO v_actor_active;
  IF NOT v_actor_active THEN RETURN false; END IF;

  UPDATE public.auth_login_proofs SET consumed_at=NOW()
  WHERE proof_hash=v_hash AND user_id=p_user_id
    AND consumed_at IS NULL AND expires_at>NOW();
  IF NOT FOUND THEN RETURN false; END IF;

  INSERT INTO public.sessions(id,token_hash,user_id,active_role,
    active_tenant_id,expires_at)
  VALUES(public.uuid_generate_v4(),v_session_hash,p_user_id,
    'PENDING_CONTEXT',NULL,NOW()+INTERVAL '90 seconds');
  RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION public.auth_issue_pending_session(uuid,text,text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auth_issue_pending_session(uuid,text,text)
  TO frcaixinha_auth_role;

DO $guard$
BEGIN
  IF has_table_privilege('frcaixinha_auth_role','public.sessions','INSERT')
    OR has_column_privilege('frcaixinha_auth_role','public.sessions','token_hash','INSERT')
    OR has_column_privilege('frcaixinha_auth_role','public.credentials','password_hash','SELECT')
    OR has_table_privilege('frcaixinha_auth_role','public.auth_login_proofs','SELECT')
    OR has_table_privilege('frcaixinha_auth_role','public.auth_login_proofs','INSERT')
    OR has_table_privilege('frcaixinha_verifier_role','public.sessions','INSERT')
    OR has_column_privilege('frcaixinha_verifier_role','public.sessions','token_hash','SELECT')
    OR has_function_privilege('frcaixinha_verifier_role',
        'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
        'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
    OR NOT has_function_privilege('frcaixinha_auth_role',
        'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
    OR NOT has_column_privilege('frcaixinha_verifier_role',
        'public.credentials','password_hash','SELECT')
  THEN RAISE EXCEPTION 'BLOQUEADO: emissao e prova de senha nao segregadas'; END IF;
END $guard$;
