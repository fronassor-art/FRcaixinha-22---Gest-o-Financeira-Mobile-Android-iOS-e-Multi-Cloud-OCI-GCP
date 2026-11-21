# FR Finance M39058 — homologação das três contas técnicas originais

## Evidência anterior
M39056: o banco original FR Finance foi comprovado (PG18.6,
127.0.0.1:5433/frcaixinha_aistudio_dev, PGDATA exclusivo do AI Studio).
M39057: a senha do verificador guardada no arquivo api.env privado
autenticou com sucesso, sem alterar senha ou banco.

## Escopo
Auditar em modo read-only os três usuários PostgreSQL do mesmo FR Finance,
usando as URLs existentes no arquivo privado original (0600):
- DATABASE_URL: frc_ai_app;
- AUTH_DATABASE_URL: frc_ai_auth;
- AUTH_VERIFIER_DATABASE_URL: frc_ai_verifier.

O M39058 reusa os controles do M39057 (caminho, permissões de arquivo,
host, porta, nome de banco, usuário) e M39055 (metadados do usuário,
permissões de tabelas, colunas e funções, segregação).
Não exibe URLs ou senhas, não solicita senha, não efetua login de usuário,
não cria sessão, não inicia ou reinicia servidor, não aplica migração,
não altera role, HBA, arquivo api.env nem banco.

Testes CI simulam credenciais; não comprovam PostgreSQL do aparelho.

## Termux original, sem sincronização destrutiva

    cd "$HOME/fr-finance"
    test -z "$(git status --porcelain --untracked-files=all)"
    git fetch origin atualizacao-ai-studio-9b46a63187
    git merge --ff-only FETCH_HEAD
    AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)" PYTHONDONTWRITEBYTECODE=1 \
      python3 -B -m backend.scripts.frfinance_m39058_three_roles_from_private_env

O operador deve conferir o SHA remoto planejado antes do merge, como
no fluxo M39057, e nunca usar reset, clone ou force.

## Interpretação
- M39058_STATUS=PASS_READ_ONLY: as três contas técnicas autenticaram
  na base correta e passaram na auditoria de permissões M39055.
- M39058_CONFIG=BLOCKED_*: URL privada ausente, alterada ou divergente.
- M39058_FRC_AI_* = INVALID_PASSWORD: revisar a credencial armazenada
  daquela role em vez de adivinhar ou redefinir a senha.
- M39058_FRC_AI_* = BLOCKED_ROLE_PERMISSION_OR_IDENTITY: inspecionar
  somente os grants/metadados antes de qualquer decisão de mudança.

Mesmo PASS não comprova login de pessoa, ativação produtiva, APK
operacional, credencial do Administrador Master ou autorização Pix.
FastAPI e homologações futuras continuam sujeitos a suas próprias
travas de segurança.
