# AI Studio — Migração local protegida (fase 1)

Data 02/11/2026. Banco exclusivo PostgreSQL 18.6 no Termux,
127.0.0.1:5433/frcaixinha_aistudio_dev.
Este projeto NÃO compartilha dados, bancos ou credenciais com outro aplicativo.

## Pré-condições
- Branch AI Studio PR #2 Draft, git limpo e HEAD igual ao SHA40 aprovado no CI.
- Ferramentas pg_dump, pg_restore, psql, age e git disponíveis.
- 0 tabelas públicas antes da primeira aplicação. Usuário do banco: frc_ai_owner.
- Os papéis frc_ai_app e frc_ai_auth já existem e NÃO são SUPERUSER/BYPASSRLS.
- Não executar SQL de outro projeto.

## Fases
1. Sincronizar GitHub para a branch exclusiva somente por fast-forward.
2. Executar preflight: AI_STUDIO_APPROVED_SHA=SHA40 bash backend/scripts/aistudio_local_migration.sh preflight.
3. Verificar banco, porta, cluster e integridade do commit.
4. Executar apply SOMENTE após leitura do resultado preflight:
   AI_STUDIO_LOCAL_MIGRATION=YES AI_STUDIO_APPROVED_SHA=SHA40 bash backend/scripts/aistudio_local_migration.sh apply.
5. Confirmar AUTORIZO_MIGRACAO_AI_STUDIO e MIGRAR_SOMENTE_AI_STUDIO interativamente.
6. Informar senha PostgreSQL e nova senha de criptografia age; não enviá-las no chat.
7. Backup criptografado é criado em ~/.local/share/frcaixinha-aistudio-mobile/backups/ com pasta 0700. O dump é verificado por descriptografia em memória sem restauração.
8. As migrações 001-027 e grants são aplicados na mesma transação via aistudio_db_local.sh, usando guarda de cluster e banco inicial vazio. Em caso de falha, interromper; não repetir cegamente.
9. Rodar verify (somente leitura) e conferir RLS, sessões e contagem do Master. As tabelas passam de zero para muitas; isso é esperado.

## Após migração
- O schema **não cria** contas humanas, Master, licença ativa ou pagamentos reais.
- Um verificador técnico de senha SEPARADO ainda precisa ser provisionado para o login.
- As URLs DATABASE_URL, AUTH_DATABASE_URL e AUTH_VERIFIER_DATABASE_URL devem apontar a usuários não privilegiados; não usar frc_ai_owner na API.
- O FastAPI precisa executar no Termux no loopback 127.0.0.1:8000 para o APK Android debug alcançá-lo.
- A inicialização do primeiro MASTER exige decisão e confirmação separadas.
- Não colocar senhas no GitHub/AI Studio/ChatGPT nem habilitar Pix, Mercado Pago ou operações financeiras reais.
- Banco restaurável exige que a senha age seja guardada de forma segura fora do telefone. Backup de database NÃO exporta senhas globais dos roles.


## Fase 2 — configurar as três conexões técnicas sem privilégios
Depois de aplicar 001-027, executar a partir da raiz, em ambiente Python com psycopg:
AI_STUDIO_LOCAL_API_SETUP=YES python3 backend/scripts/aistudio_local_api_setup.py

Assistente solicita senha do owner e senhas já existentes dos papéis frc_ai_app
e frc_ai_auth (mínimo 12 caracteres). Não enviar ao chat. Cria role SQL
frc_ai_verifier exclusiva, gerando nova senha forte, sem papel Master e sem
permissão de emitir sessões diretamente. Arquivo api.env é criado em
~/.config/frcaixinha-aistudio-mobile/api.env, modo 0600; script recusa
sobrescrever arquivo existente. Se qualquer etapa falhar, parar e auditar.
O operador deve proteger o aparelho com senha/biometria e não copiar api.env
para repositório, IA Studio, ZIP ou storage público.

Executar depois bash backend/scripts/run_termux_fastapi.sh em uma sessão
Termux persistente; o backend deverá responder em http://127.0.0.1:8000.
Confirmar GET /api/health/ready = 200 e READY_FOR_TEST_AUTH antes de
qualquer provisionamento de conta.
