-- AI Studio: principio do menor privilegio para o papel de aplicacao.
-- Aplica-se SOMENTE apos 001-011, em PostgreSQL de homologacao primeiro.
-- A autenticacao possui papel separado (frcaixinha_auth_role), com acesso minimo
-- a email/credenciais. O papel financeiro NUNCA deve consultar CPF/email/hash.
-- O schema users permanece sem RLS; esta medida reduz COLUNAS visiveis, nao
-- substitui isolamento por tenant em toda consulta que contenha dados pessoais.
REVOKE SELECT ON TABLE public.users FROM PUBLIC, frcaixinha_app_role;
GRANT SELECT (id, full_name) ON TABLE public.users TO frcaixinha_app_role;

DO $assert$
BEGIN
  IF has_column_privilege('frcaixinha_app_role','public.users','cpf','SELECT')
    OR has_column_privilege('frcaixinha_app_role','public.users','email','SELECT')
    OR has_column_privilege('frcaixinha_app_role','public.users','phone','SELECT')
    OR has_column_privilege('frcaixinha_app_role','public.users','is_master','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: papel aplicativo ainda le dados privados de identidade';
  END IF;
  IF NOT has_column_privilege('frcaixinha_app_role','public.users','id','SELECT')
     OR NOT has_column_privilege('frcaixinha_app_role','public.users','full_name','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: consultas minimizadas perderam colunas de identificacao';
  END IF;
  IF NOT has_column_privilege('frcaixinha_auth_role','public.users','email','SELECT')
     OR has_column_privilege('frcaixinha_auth_role','public.users','cpf','SELECT')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: privilégio de autenticacao incorreto';
  END IF;
END
$assert$;
