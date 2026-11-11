# FR Finance M38996 — ligar cadastro Brevo anterior ao api.env original

## O que estava comprovado

Em 11/11/2026, a auditoria `M38995` no Termux observou:
- Projeto único em `$HOME/fr-finance`, branch `atualizacao-ai-studio-9b46a63187`;
- PostgreSQL 18 original `frcaixinha_aistudio_dev` porta `5433`, API existente porta `8000`, rotas `POST /api/v1/auth/reset-password`, `POST /api/v1/invitations/verify-email` e `POST /api/v1/invitations` montadas;
- Migrações **047 e 048 já aplicadas** com direitos corretos; **não repetir**;
- Arquivo privado original `$HOME/.config/frcaixinha-aistudio-mobile/api.env` com `AUTH_DATABASE_URL` mas **sem** as variáveis de envio;
- Cadastro público anterior `$HOME/.config/frfinance-aistudio/provider-public-inputs.json` com **todos os cinco campos de e-mail/APP_URL já preenchidos**;
- Evidência manual de 08/11 da Brevo: domínio e remetente autenticados, SMTP aceito e mensagem de teste recebida. **Não recadastrar domínio, remetente ou conta na Brevo**.

## O que o M38996 faz agora

O script `backend/scripts/frfinance_m38996_stage_existing_mail_config.py` possui modos:

- `inspect` — confere branch, banco de autenticação original, arquivo 0600 e cadastro existente, sem alterar nada;
- `stage-public` — copia apenas `APP_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `FR_FINANCE_EMAIL_FROM` **do cadastro público já registrado** ao *mesmo* `api.env`, mantendo todas as linhas existentes. Se o valor já existir e for igual, não duplica; se divergir, bloqueia para revisão. Não substitui o banco;
- `stage-private` — faz o mesmo e, **somente se faltar**, solicita a chave SMTP já emitida pela Brevo em prompt local oculto, além de gerar uma chave AES-256-GCM e uma chave HMAC para o mecanismo de fila. Chaves já existentes são preservadas. A gravação é atômica, somente no **mesmo arquivo privado** com permissões 0600, sem criar diretório ou repositório.

O script **não declara** `FR_FINANCE_ACCESS_MAIL_ENABLE=REVIEWED_SINGLE_DB`, `FR_FINANCE_ACCESS_MAIL_WORKER=EXPLICITLY_APPROVED`, flags de ativação de usuários ou Pix. Não há envio SMTP, conexão nova com banco, alteração de estrutura SQL ou cloud.

### Atenção ao APP_URL

O campo `APP_URL` já cadastrado representa a **URL HTTPS planejada**, não a prova de um servidor publicado. Copiá-la ao `api.env` **não disponibiliza** links para convidados até que o conteúdo do aplicativo esteja hospedado nesse endereço. Por isso, não ativar e-mails/worker nem testar com convidados reais antes de confirmar HTTPS e o destinatário de homologação.

### Segurança / próxima liberação

A chave SMTP, se solicitada, deve ser introduzida **somente no Termux**, sem chat, GitHub, capturas ou logs. O arquivo local 0600 serve exclusivamente à homologação controlada; na Oracle, secrets devem ficar em solução de cofre/IAM apropriada. O teste real da fila deve usar uma caixa de e-mail consentida, envio explicitamente autorizado e credenciais de homologação. Provar conexão SMTP isolada não equivale a envio pelo outbox.

Depois da sincronização execute `PYTHONPATH=backend python backend/scripts/frfinance_m38996_stage_existing_mail_config.py inspect`; em seguida use `stage-private` para preparar o arquivo e execute `inspect` novamente. Ainda não reinicie a FastAPI para ativar worker: o script não altera flags nem a API já executando. A Oracle permanece na última fase.
