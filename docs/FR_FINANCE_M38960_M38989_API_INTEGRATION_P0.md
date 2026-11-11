# FR Finance — Conectar os fluxos reais à FastAPI existente (P0)

## Objetivo: finalizar pontos essenciais, não repetir o projeto

**Único repositório:** `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`, branch `atualizacao-ai-studio-9b46a63187`. **Único projeto Termux:** `$HOME/fr-finance`; banco lógico original `frcaixinha_aistudio_dev`, PostgreSQL 18 porta 5433. **Única FastAPI:** `backend/app/main.py` porta 8000. O FR Caixinha 2.2 está excluído.

## O que foi de fato implementado nesta entrega

1. **Convites:** a rota pública existente `POST /api/v1/invitations` passa por `submit_invitation_to_existing_outbox`, revalida papel de administrador e parâmetros mínimos e delega a um serviço transacional protegido. **Sem serviço injetado retorna 503.** O cadastro Master permanece bloqueado até MFA + dupla aprovação.
2. **Recuperação de senha:** a rota existente `POST /api/v1/auth/forgot-password` passa por `submit_password_recovery_to_existing_outbox`. Apenas um evento **realmente persistido** na fila original pode produzir HTTP 202; nenhuma resposta de teste pode alegar envio. O resultado nunca revela a existência da conta, e o cliente Android interpreta somente o contrato de resposta 202, sem aceitar JSON falso.
3. **Tela Android:** o botão "Esqueci a senha" agora usa `authService.requestPasswordReset` (já existente), mostra indisponibilidade sem prometer e-mail e só confirma uma solicitação aceita pela API.
4. **Mercado Pago Orders:** `/integrations/mercadopago/orders` usa o validador HMAC original `mp_orders_webhook.create_orders_staging_router`, registrado **na mesma FastAPI**. O callback requer HTTPS, secret de assinatura, mapeamento do vendedor e inbox transacional; sem serviços verificados retorna erro. **Não altera ledger, não marca obrigações pagas**.
5. **Mercado Pago OAuth:** `GET /api/v1/mercadopago/oauth/callback` utiliza a mesma FastAPI, valida formato de state/code e HTTPS e exige a conclusão via serviço que comprove estado PKCE consumido uma vez, tenant/vendedor vinculado e token cifrado. Sem serviço protegido retorna 503. Dinheiro real permanece OFF.

## Pendências reais, não análises extras

O código de preparação para SMTP já está no módulo `backend/app/onboarding_mail_transport.py`, e o teste manual de 8/11 comprovou recebimento de um SMTP real pela Brevo. **Não repetir cadastro de domínio, senha SMTP ou envio sintético como se fossem tarefas novas.**

O que falta para completar o acesso real é **ligar uma implementação transacional durável no banco original**, com identidade/contrato/tenancy/MFA, token único cifrado, mecanismo de retry, fila de envio pós-commit, entrega confirmada e sessão revogada na troca de senha. Os SQL de staging `050_invitation_outbox_staging_only.sql` e `051_password_reset_staging_only.sql` **NÃO podem ser aplicados diretamente no banco Termux**; possuem guardas exclusivamente para CI. Nesta entrega, nenhuma migration foi aplicada e nenhum novo banco ou diretório foi criado.

No Mercado Pago, os adaptadores HMAC/OAuth/Orders já existem. Para conexão real ainda faltam **URI HTTPS pública registrada**, seller registry validado, persistência segura de estado/token, worker de inbox idempotente e habilitação do provedor para o uso comercial; Pix saída demanda aprovação específica de Money Out. Os novos endpoints recebem eventos somente quando o deployment fornecer as dependências verificadas. **A montagem do endpoint não é a ativação do webhook no provedor.**

## Verificação rápida antes de recomeçar qualquer diagnóstico

No Termux:

```bash
cd "$HOME/fr-finance"
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python backend/scripts/frfinance_m38800_existing_services_probe.py local AUTHORIZE_FRFINANCE_EXISTING_SERVICES_READONLY
```

Se PostgreSQL estiver ligado em 5433 e a FastAPI desligada em 8000, iniciar apenas **o script existente** `bash backend/scripts/run_termux_fastapi.sh` (numa sessão Termux dedicada) sem criar serviço substituto. A execução de testes pode ocorrer em outra sessão no **mesmo** worktree.

**Não repetir os 12.875 testes homologados como pré-requisito permanente**: executar a suíte focal de convite, recuperação e webhook; usar CI completa apenas na preparação de release ou mudança de risco.

## Requisitos para liberação

- Não ativar emissão real de convites ou reset enquanto o outbox transacional e autenticação de e-mail não tiverem teste operacional com conta consentida.
- Não habilitar Pix real sem prova de pagamento, recebimento webhook, conciliação bancária e ledger atômico.
- Prioridade de implantação: concluir links de código e homologação com serviços de teste existentes; Oracle VM fica para a última fase segundo o plano do proprietário, com possível opção paga apenas a partir de **30/11/2026**.


## M38990 — execução efetiva no mesmo banco existente (ainda NÃO aplicada)

No código da MESMA FastAPI foram adicionados:
- \`backend/app/access_delivery_pg18.py\`: emissão de tokens de uso único e envelopes AES-256-GCM, transação asyncpg de criação de convite e recuperação, recibo pós-commit, fila cifrada, consumidor de Brevo com captura de aceite SMTP e quarentena de resultados incertos, **sem confirmação falsa de entrega**.
- \`backend/local_migrations/047_frfinance_access_delivery_outbox.sql\`: **migração candidata, aditiva**, uma tabela de fila e quatro funções restritas ao papel existente \`frc_ai_auth\`; não cria banco, PostgreSQL, FastAPI, diretório, usuário final ou role nova. Guarda pelo DB \`frcaixinha_aistudio_dev\`, porta 5433, PGDATA exato, versão 18, proprietário \`frc_ai_owner\` e aprovação específica \`frfinance.migration_047_approved=1\`.
- A instalação só ocorre no startup da FastAPI existente quando \`FR_FINANCE_ACCESS_MAIL_ENABLE=REVIEWED_SINGLE_DB\`, \`FR_FINANCE_OUTBOX_047_VERIFIED=YES\`, \`FR_FINANCE_SMTP_OPERATOR_APPROVED=YES\`, \`ENVIRONMENT=homologation\`, \`FRCAIXINHA_TERMUX_LOCAL_API=1\` e o domínio/SMTP/DSN originais estiverem configurados. O consumidor só é iniciado no mesmo processo após \`FR_FINANCE_ACCESS_MAIL_WORKER=EXPLICITLY_APPROVED\`. **Nenhuma dessas flags deve ser ligada apenas porque os testes sintéticos passaram.**

**Estado neste commit:** migração 047 versionada, **não aplicada ao PostgreSQL do celular**; autenticação, SMTP e Pix reais não são automaticamente habilitados. Não copiar migrações de staging 050/051; são exclusivas da CI. Antes de aplicar M047, conferir que o objeto ainda não existe no banco original, que a FastAPI usa as roles existentes, e executar testes direcionados. A aplicação da migração é outra operação, sujeita a controle do banco real, não parte do \`git merge --ff-only\`.

**Ainda necessário para ativar contas:** implementar o consumo autenticado dos tokens de convite/recuperação (aceite contratual comprovado, mudança de senha Argon2id e revogação de sessões); confirmar o envio end-to-end em uma caixa postal consentida; obter HTTPS público definitivo. Uma fila SMTP funcional sozinha não equivale a cadastro/recuperação completos.

**Ainda necessário para Pix:** persistência operacional do seller OAuth/PKCE e callback, inbox assinada, conciliação bancária e autorização de Payouts/Money Out. Nenhuma operação financeira real é autorizada pelo M38990.
