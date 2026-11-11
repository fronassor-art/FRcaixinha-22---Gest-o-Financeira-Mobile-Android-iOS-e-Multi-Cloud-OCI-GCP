# FR Finance — M38993/38994 | Concluir consumo de links de convite e recuperação

## Evidência local confirmada

Em 11/11/2026 o Termux, no único worktree `$HOME/fr-finance`, sincronizou `19acd8a`. Executou **36 testes PASS**, catálogo SQL íntegro (110 arquivos na época), PostgreSQL 18 **online** porta 5433 e FastAPI existente **online** porta 8000. O usuário autorizou a migração local 047 para **`frcaixinha_aistudio_dev`**, e a operação retornou **`COMMIT` + `M38992_MIGRATION_047=SCHEMA_APPLIED`**; backup custom format anterior validado por listagem no Termux. **Não reaplicar a 047.** Restauração do arquivo não foi ensaiada.

## Implementado neste pacote

- `backend/local_migrations/048_frfinance_access_token_redemption.sql`: **duas funções novas**, nenhuma tabela, nenhuma role/cluster/usuário adicional. Executam como SECURITY DEFINER do proprietário original, com acesso concedido somente a `frc_ai_auth`.
- `public.frfinance_verify_invite_email(char(64))`: compara hash SHA256 com evidência de link enviado e ainda válido, bloqueia uso repetido e registra comprovação de titularidade de e-mail. **Não cria conta, membro ou aceite contratual.**
- `public.frfinance_redeem_reset_token(char(64),varchar(255))`: exige token de uso único, marca entrega comprovada pela posse e consumo do token, salva **somente hash Argon2id** na tabela original de credenciais e revoga todas as sessões anteriores e demais tokens de recuperação ainda não consumidos. A operação é atômica e serializada por conta.
- `backend/app/access_delivery_pg18.py`: métodos de resgate no **mesmo** `frc_ai_auth`; valida senha no backend e calcula Argon2id em thread. Os métodos só são montados com `FR_FINANCE_ACCESS_REDEMPTION_048_VERIFIED=YES` **após inspeção real das funções na base original**. No Termux, as flags seguem OFF.
- `backend/app/routers/auth.py`: **POST `/api/v1/auth/reset-password`**, sem conta nova.
- `backend/app/routers/invitations.py`: **POST `/api/v1/invitations/verify-email`**, sem ativação de membro.
- `src/components/AccessLinkView.tsx`, `LoginView.tsx`, `authService.ts`: links já utilizados pelo adaptador Brevo (`/#recuperacao?token=...` e `/#convite?token=...`) agora têm telas reais; o fragmento é retirado do histórico antes de usar o token no POST, e token/senha não são guardados em armazenamento persistente.
- `backend/scripts/frfinance_m38994_apply_m048_original_pg18.sh`: instalador específico da 048, com confirmação explícita, guarda de projeto/PGDATA/porta/versão, conferência da **cópia existente da etapa 047** e revisão das permissões após o SQL. **Não cria novo backup ou diretório**; não repete 047.

## Importante

**Atualização de checkpoint M38994 (11/11/2026):** o usuário aplicou a 048 **no banco original** `frcaixinha_aistudio_dev`, porta `5433`; o SQL retornou `COMMIT`, a validação das funções/permissões passou, e a 047 permaneceu intacta. **Não reaplicar as migrações 047 nem 048.** A CI `a5050d5` também concluiu com sucesso. O código de consumo da 048 está versionado e instalado no banco, mas envio real e ativação permanecem bloqueados. Os testes sintéticos não substituem ensaio da função em uma conta consentida. O instalador original exige aprovação explícita `APLICAR_M048_FR_FINANCE` e já foi utilizado com sucesso; não executar novamente. Falha de qualquer verificação interrompe a operação. A 048 exige as tabelas e índices antigos intactos e não altera dados até que um link real válido seja apresentado.

**Após a evidência de M048 no Termux:** 1) localizar e configurar sob aprovação as variáveis de outbox e worker já existentes, 2) provar envio pela Brevo com caixa de e-mail consentida e recebimento do link, 3) verificar os endpoints de consumo e comportamento de replay/revogação, 4) implementar ou integrar o aceite contratual e habilitação de membro usando mecanismos de identidade já versionados. O e-mail enviado não equivale a consentimento contratual. A habilitação financeira ou Pix real permanece OFF.

**Infraestrutura Oracle:** etapa separada e final, conforme planejamento do proprietário (consideração de VM paga em 30/11/2026 se a gratuita não surgir).


## M38995 — preservar evidência Brevo e localizar configuração, sem repetição

O checkpoint manual **M28500 de 08/11/2026** já registrava domínio `frfinance.com.br` autenticado na Brevo, remetente `notificacoes@frfinance.com.br` verificado, SMTP STARTTLS aceito em teste isolado e uma mensagem recebida em uma caixa autorizada. Esses resultados **não exigem recadastrar domínio, remetente ou chave**; também não provam que a FastAPI esteja enviando e-mails agora.

Na auditoria do Termux de 11/11: banco 5433 e FastAPI 8000 online; funções 047/048 presentes com grants corretos, mas a API **ainda executava o processo anterior às rotas**. `api.env` tinha `AUTH_DATABASE_URL`, porém não declarava `APP_URL`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `FR_FINANCE_EMAIL_FROM` ou flags de envio. Esse fato **não implica ausência dos dados públicos** previamente cadastrados em `$HOME/.config/frfinance-aistudio/provider-public-inputs.json`, arquivo separado e preservado.

O script `backend/scripts/frfinance_m38995_access_runtime_readonly.py` **não grava dados**, verifica somente o projeto/branch original, existência de chaves em `api.env`, existência de campos no intake público anterior e rotas da API local; nunca exibe valores ou autentica SMTP. A execução deve ocorrer **após sincronizar a mesma branch**, sem mexer na API, PostgreSQL, diretórios ou nas migrações. Se as rotas não aparecerem, interromper a FastAPI na sessão original com Ctrl+C e reiniciá-la com `bash backend/scripts/run_termux_fastapi.sh` após o git sync.

Antes de qualquer envio transacional real é necessário confirmar uma **URL HTTPS que abra o aplicativo** (o domínio DNS de e-mail sozinho não garante isso), credenciais Brevo instaladas com proteção adequada, configuração e aprovação de worker de outbox, e destinatário de homologação consentido. Não ativar membros ou Pix automaticamente; OCI permanece para a fase final prevista.
