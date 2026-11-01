-- O papel transacional não deve ler ou alterar hashes de todas as contas.
-- A futura autenticação precisa de um papel/serviço próprio e acesso mínimo.
REVOKE ALL PRIVILEGES ON TABLE public.credentials FROM PUBLIC, frcaixinha_app_role;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.users FROM PUBLIC, frcaixinha_app_role;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE public.audit_events FROM PUBLIC, frcaixinha_app_role;
