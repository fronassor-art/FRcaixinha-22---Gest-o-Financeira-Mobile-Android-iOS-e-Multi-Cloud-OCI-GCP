# FR Finance AI Studio — SUPERPACOTE M25400–M25600

Repositório e branch da frente **AI Studio**, isolada de qualquer outro
projeto. Alterações versionadas, sem migrar o banco local nem ativar PIX real.

## M25400 — Conteúdo contratual canônico (funcional se provisionado)

- Rota protegida `POST /api/v1/invitations/preflight/contract-content`.
- Verifica papel, tenant ativo e documento `TENANT_MEMBERSHIP` publicado
  pelo banco com RLS, *antes* de acessar o arquivo.
- Diretório absoluto configurado por `FR_FINANCE_CANONICAL_CONTRACT_DIR`;
  arquivo com nome exato `<UUID>.txt`. Nada de paths recebidos do cliente.
- Abre diretório e arquivo por descritores com `O_NOFOLLOW`, rejeita
  symlink, arquivo mutável, ausência, bytes acima de 65536, UTF-8 inválido
  e SHA-256 incompatível.
- Em **produção**, requer que o usuário Unix do processo API não seja dono
  do diretório e do arquivo imutável. Provisionamento deve garantir que os
  arquivos sejam de operador separado e acessíveis só para leitura.
- Cliente React carrega o conteúdo canônico e recalcula SHA-256 via WebCrypto;
  mantém sem assinatura/aceite/cadastro.
- Somente texto UTF-8, não um PDF. Conteúdo jurídico aprovado **não está**
  incluído no repositório e deve ser provisionado pelo responsável autorizado.

## M25500 — Transporte SMTP com STARTTLS

- Adaptador `onboarding_mail_transport.py` exige URL pública HTTPS,
  hostname SMTP público, remetente válido e porta 587 STARTTLS.
- Testes sem rede verificam falhas TLS, injeção de cabeçalho, tokens opacos,
  recusa de destinatário e neutralidade de exceções.
- Retorno `smtp_accepted=true` **NÃO** significa entregue ou e-mail verificado.
- Não invocar diretamente nas rotas públicas. Falta um worker durable outbox:
  mensagem idempotente, transação, retry, bounce, webhook, segredo em vault,
  e validação de domínio/provedor.
- Links são fragmentos: aplicativo futuro deve implementar fluxo de
  leitura do fragmento e POST de token protegido, sem logar URL.
- A rota de recuperação de senha segue 503, até que a transação de tokens
  e entrega esteja implementada e aprovada.

## M25600 — Mapa de conclusão sem lacunas silenciosas

- `GET /api/v1/master/launch-readiness`, exigindo `require_master`.
- Painel em "Preparação de administradores", visível somente ao Master.
- Retorna 20 etapas agrupadas em identidade, cadastro, infraestrutura e
  pagamentos. Todas exigem evidência de integração antes da produção.
- Faz somente verificação sintática local de APP_URL, SMTP e autenticação
  de produção; **nunca** afirma DNS/TLS, credenciais funcionais,
  pagamento ou hospedagem efetivos.
- O painel não grava nem altera flags nem inicia operações de produção.

## Bloqueios de terceiros e ações objetivas

1. **Termux e banco:** comprovar histórico local das migrações, sobretudo
   028–030, 034–044, além das políticas RLS. O catálogo de 73 arquivos SQL
   íntegros **não é** atestado de aplicação local. Usar modo local-readonly
   com SHA explicitamente aprovado e senha oculta. Jamais aplicar CI/staging
   SQL ao banco Termux por correspondência de número.
2. **Contratos:** fornecer texto UTF-8 de adesão validado juridicamente e
   conferir SHA-256 com `public.contract_documents`; usar diretório
   imutável fora do repositório.
3. **SMTP:** domínio/remetente autorizado, senha em gestor de segredos,
   confirmação de conta e operabilidade real; sem expor token em terminal.
4. **Cadastro:** implantar funções SQL transacionais com privilégio mínimo
   para emitir, verificar, revogar e aceitar convites, mais outbox e rate
   limiting distribuído; validar no staging OCI, não na porta 5433 diretamente.
5. **Segurança administrativa:** MFA e aprovação independente real;
   conta Master existente não deve ser recriada.
6. **OCI:** domínio/TLS, VM/containers, PostgreSQL segregado, backup
   restaurável, observabilidade, versão runtime e deploy auditable.
7. **Mercado Pago:** OAuth multi-tenant, secret store e webhooks de eventos
   assinados, Orders Pix de cobrança e Money Out apenas se autorizado pelo PSP.
   Não movimentar dinheiro sem conciliação e testes contratuais completos.
8. **Android:** CI faz APK debug, não substitui assinatura release, instalação,
   teste de rede pública e homologação no celular.

## Testes obrigatórios

- `backend/tests/test_m25400_canonical_contract_delivery_ci.py`.
- `backend/tests/test_m25500_onboarding_smtp_transport_ci.py`.
- `backend/tests/test_m25600_launch_readiness_ci.py`.
- `src/tests/m25400_canonical_contract_ui_ci.test.ts`.
- `src/tests/m25600_launch_readiness_ui_ci.test.ts`.
- Regressões M24900–M25300, RLS e build APK mantidos no workflow.

## Estados que não podem ser falsamente liberados

`real_invites_active=false`;
`password_reset_active=false`;
`real_pix_active=false`;
`financial_closing_authorized=false`.

O objetivo é eliminar pendências por implementação, integração e verificação
separadamente. Um gate operacional não deve ser eliminado apenas para
apresentar um checklist visualmente completo.
