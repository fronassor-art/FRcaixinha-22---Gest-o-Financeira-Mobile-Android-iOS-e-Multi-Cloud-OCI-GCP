-- AI Studio 026 (P0-01g) — prova vinculada à credencial e revogação em rotação.
-- SOMENTE PostgreSQL DESCARTÁVEL do CI. NÃO aplicar ao banco Termux.
-- Migration não provisiona usuários, senhas, serviços nem recursos financeiros.

-- Provas já existentes sem fingerprint tornam-se inutilizáveis, sem exclusão.
ALTER TABLE public.auth_login_proofs
  ADD COLUMN credential_fingerprint text;
ALTER TABLE public.auth_login_proofs
  ADD CONSTRAINT auth_proof_fingerprint_format
  CHECK (credential_fingerprint ~ '^[0-9a-f]{64}$') NOT VALID;

GRANT INSERT (credential_fingerprint)
  ON public.auth_login_proofs TO frcaixinha_verifier_role;

DROP POLICY auth_proof_verifier_insert ON public.auth_login_proofs;
CREATE POLICY auth_proof_verifier_insert
  ON public.auth_login_proofs FOR INSERT TO frcaixinha_verifier_role
  WITH CHECK (
    consumed_at IS NULL
    AND expires_at <= created_at + INTERVAL '90 seconds'
    AND credential_fingerprint ~ '^[0-9a-f]{64}$'
  );

-- A atualização/remoção da credencial invalida provas pendentes e todas as
-- sessões do usuário (inclusive sessões de outros contextos/tenants).
CREATE FUNCTION public.auth_invalidate_on_credential_change()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp
AS $$
DECLARE v_user_id uuid;
BEGIN
  v_user_id := CASE WHEN TG_OP='DELETE' THEN OLD.user_id ELSE NEW.user_id END;
  UPDATE public.auth_login_proofs SET consumed_at=NOW()
  WHERE user_id=v_user_id AND consumed_at IS NULL;
  UPDATE public.sessions SET revoked_at=NOW()
  WHERE user_id=v_user_id AND revoked_at IS NULL;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.auth_invalidate_on_credential_change()
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;

CREATE TRIGGER auth_password_changed_revoke
AFTER UPDATE OF password_hash ON public.credentials
FOR EACH ROW
WHEN (OLD.password_hash IS DISTINCT FROM NEW.password_hash)
EXECUTE FUNCTION public.auth_invalidate_on_credential_change();

CREATE TRIGGER auth_password_deleted_revoke
AFTER DELETE ON public.credentials
FOR EACH ROW
EXECUTE FUNCTION public.auth_invalidate_on_credential_change();

-- Ordem consistente dos bloqueios: credentials (FOR SHARE) -> proof (FOR UPDATE).
-- Uma rotação concorrente aguarda a emissão e revoga a sessão resultante, ou
-- vence antes da leitura da credencial e invalida o fingerprint anterior.
CREATE OR REPLACE FUNCTION public.auth_issue_pending_session(
  p_user_id uuid, p_raw_session_token text, p_raw_proof text
)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp
AS $$
DECLARE
  v_hash text;
  v_session_hash text;
  v_credential_fingerprint text;
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

  SELECT encode(public.digest(c.password_hash,'sha256'),'hex')
    INTO v_credential_fingerprint
  FROM public.credentials c WHERE c.user_id=p_user_id FOR SHARE;
  IF NOT FOUND THEN RETURN false; END IF;

  PERFORM 1 FROM public.auth_login_proofs p
  WHERE p.proof_hash=v_hash AND p.user_id=p_user_id
    AND p.credential_fingerprint=v_credential_fingerprint
    AND p.consumed_at IS NULL AND p.expires_at>NOW()
  FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;

  SELECT EXISTS(
    SELECT 1 FROM public.users
    WHERE id=p_user_id AND status='ACTIVE'
  ) INTO v_actor_active;
  IF NOT v_actor_active THEN RETURN false; END IF;

  UPDATE public.auth_login_proofs SET consumed_at=NOW()
  WHERE proof_hash=v_hash AND user_id=p_user_id
    AND credential_fingerprint=v_credential_fingerprint
    AND consumed_at IS NULL AND expires_at>NOW();
  IF NOT FOUND THEN RETURN false; END IF;

  INSERT INTO public.sessions(id,token_hash,user_id,active_role,
    active_tenant_id,expires_at)
  VALUES(public.uuid_generate_v4(),v_session_hash,p_user_id,
    'PENDING_CONTEXT',NULL,NOW()+INTERVAL '90 seconds');
  RETURN true;
END;
$$;

-- Um papel SQL comprometido, isoladamente, não pode substituir a função.
REVOKE ALL ON FUNCTION public.auth_issue_pending_session(uuid,text,text)
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.auth_issue_pending_session(uuid,text,text)
  TO frcaixinha_auth_role;

DO $guard$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM pg_trigger
      WHERE tgrelid='public.credentials'::regclass
        AND tgname='auth_password_changed_revoke' AND NOT tgisinternal
    )
    OR NOT EXISTS (
      SELECT 1 FROM pg_trigger
      WHERE tgrelid='public.credentials'::regclass
        AND tgname='auth_password_deleted_revoke' AND NOT tgisinternal
    )
    OR has_table_privilege('frcaixinha_auth_role','public.auth_login_proofs','SELECT')
    OR has_column_privilege('frcaixinha_auth_role','public.credentials','password_hash','SELECT')
    OR has_table_privilege('frcaixinha_auth_role','public.sessions','INSERT')
    OR has_function_privilege('frcaixinha_verifier_role',
         'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
    OR NOT has_column_privilege('frcaixinha_verifier_role',
         'public.auth_login_proofs','credential_fingerprint','INSERT')
  THEN RAISE EXCEPTION 'BLOQUEADO: prova de credencial ou revogação não segregada'; END IF;
END $guard$;
