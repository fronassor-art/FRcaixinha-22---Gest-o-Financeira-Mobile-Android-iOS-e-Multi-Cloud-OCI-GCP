# M21600 — Preparação de segurança CORS para OCI, sem provisionamento

O backend FastAPI do FR Finance AI Studio mantém localhost somente em desenvolvimento/homologação. Em production, a lista CORS é derivada exclusivamente de APP_URL como origem pública HTTPS (domínio, sem path, query, fragment, credenciais ou porta não padronizada). APP_URL inválida resulta em lista vazia: bloqueio, não fallback para localhost.

Esta proteção reduz o risco de o backend de produção aceitar origens de navegador não autorizadas. Não é prova de domínio, certificado, posse de sessão ou separação de tenant. CORS não substitui autorização server-side, CSRF quando aplicável, RLS e autenticação.

## Pendência crítica para lançamento

O módulo backend/app/dependencies.py, função auth_database_url, **nega explicitamente produção**; backend/app/routers/auth.py reporta homologação. Não remover esse bloqueio por uma variável isolada. A autenticação de produção precisa de design/revisão de papéis PostgreSQL, TLS ou socket privado comprovado, rate limit distribuído, rotação, recuperação de senha, persistência, revogação, testes ponta a ponta em staging OCI e aprovação independente.

## Gate de hospedagem

1. Testar no Termux sem dinheiro real e verificar resultado M21500.
2. Implementar autenticação de produção separada e auditar permissões com roles sem SUPERUSER/BYPASSRLS.
3. Definir domínios APP_URL e VITE_API_URL HTTPS; obter certificados; validar PKI.
4. Implementar backups criptografados e restauração, aplicação de migrações revisadas, observabilidade e backups no destino OCI Always Free.
5. Registrar webhook de testes, verificar assinatura por seller, idempotência, GET Orders, reconciliação com fontes independentes.
6. Homologar Android três perfis em conexão externa; só então avaliar chave de assinatura/distribuição.
7. Restringir ingress, egress, IAM e custos; nenhum Terraform apply foi executado.

CI M21600 testa origens hostis, domínio HTTPS, origem inválida bloqueada e preservação do ambiente local. Nenhuma configuração OCI real foi aplicada.
