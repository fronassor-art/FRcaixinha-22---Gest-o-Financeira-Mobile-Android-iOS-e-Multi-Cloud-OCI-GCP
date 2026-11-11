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

O código de consumo da 048 foi **publicado, mas a migração ainda não foi aplicada**. Os testes sintéticos não substituem ensaio da função em uma conta consentida. O operador só deve usar o instalador após CI/Termux PASS; ele solicita literalmente `APLICAR_M048_FR_FINANCE`. Falha de qualquer verificação interrompe a operação. A 048 exige as tabelas e índices antigos intactos e não altera dados até que um link real válido seja apresentado.

**Após a aplicação e evidência em Termux:** 1) homologar e ativar sob aprovação as variáveis de outbox e worker já existentes, 2) provar envio pela Brevo com caixa de e-mail consentida e recebimento do link, 3) verificar os endpoints de consumo e comportamento de replay/revogação, 4) implementar ou integrar o aceite contratual e habilitação de membro usando mecanismos de identidade já versionados. O e-mail enviado não equivale a consentimento contratual. A habilitação financeira ou Pix real permanece OFF.

**Infraestrutura Oracle:** etapa separada e final, conforme planejamento do proprietário (consideração de VM paga em 30/11/2026 se a gratuita não surgir).
