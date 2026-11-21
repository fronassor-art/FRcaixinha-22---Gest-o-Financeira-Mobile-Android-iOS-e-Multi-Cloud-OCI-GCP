# FR Finance M39060 — Divergência de configuração entre disco e FastAPI existente

## Fatos comprovados em 12/11/2026 no Termux
- M39058: 25 testes offline PASS, três credenciais privadas e permissões
  de frc_ai_app, frc_ai_auth e frc_ai_verifier passaram no PG18.6 de
  FR Finance (frcaixinha_aistudio_dev, porta 5433).
- M39059: 11 testes offline PASS, FastAPI FR Finance ONLINE em
  127.0.0.1:8000, duas rotas privadas devolveram 401, CORS Android PASS.
- Entretanto, /auth/status retornou BLOCKED_PENDING_CONFIG e
  /api/health/ready retornou HTTP 503.

## Hipótese fundada no código
O backend/app/routers/auth.py devolve BLOCKED_PENDING_CONFIG quando
settings.is_database_configured é falso, isto é, DATABASE_URL não estava
configurado no momento da inicialização do processo.

O backend/scripts/frfinance_m39051_local_apk_api.py, no modo --serve,
limpa DATABASE_URL, AUTH_DATABASE_URL e AUTH_VERIFIER_DATABASE_URL
propositadamente para visualização segura do APK (sem login). Isso pode
explicar o serviço ativo, mas NÃO foi comprovado qual comando criou o
processo e não se deve presumir sua origem.

A configuração privada existente no disco NÃO modifica automaticamente
a configuração de um processo FastAPI já iniciado.

## Escopo M39060
- Exigir worktree, branch e SHA originais do FR Finance.
- Reutilizar M39058 para validar as três URLs do arquivo privado 0600,
  sem imprimir seus valores e sem autenticação SQL adicional.
- Verificar somente presença/adequação de flags de homologação no
  mesmo arquivo (não exibir chaves, senhas, URLs ou conteúdo completo).
- Fazer apenas GET de /api/health e /api/v1/auth/status na
  FastAPI já existente em 127.0.0.1:8000, sem proxy ou redirecionamento.
- Classificar diferença entre DATABASE_URL privado e DATABASE_URL ativo,
  sem acessar /proc/PID/environ, iniciar, parar ou reiniciar qualquer processo.

Mesmo PASS_READ_ONLY_DIAGNOSIS significa diagnóstico concluído, NÃO
significa que login humano está liberado.

## Execução no Termux original

    cd "$HOME/fr-finance"
    # Se houver mudanças locais, pare e revise em vez de executar reset.
    test -z "$(git status --porcelain --untracked-files=all)"
    git fetch --no-tags origin atualizacao-ai-studio-9b46a63187
    # Conferir SHA exato publicado e mesclar SOMENTE por fast-forward.
    git merge --ff-only FETCH_HEAD
    AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)" PYTHONDONTWRITEBYTECODE=1 \
      python3 -B -m backend.scripts.frfinance_m39060_live_vs_private_api_config

## Interpretação
- DISK_HAS_VALID_DSNS_BUT_ACTIVE_API_DATABASE_URL_EMPTY:
  arquivo privado possui alvos corretos; processo ativo está sem URL
  financeira carregada, compatível com modo visual M39051 ou inicialização
  sem carregar api.env.
- ACTIVE_API_AUTH_FLAGS_OR_CREDENTIALS_NOT_LOADED: conexão principal
  presente na API, mas chaves/flags de modo de teste não aceitas.
- ACTIVE_API_TEST_MODE_READY_REQUIRES_SEPARATE_READINESS:
  exigir nova sondagem M39059 para liberação da homologação.
- SAVED_TEST_AUTH=NOT_ENABLED ou SAVED_RATE_LIMIT_KEY=MISSING_OR_SHORT:
  configuração no disco exige revisão ANTES de qualquer reinício.

**Não fazer** kill/pkill, restart, reexecutar --serve, reset,
ALTER ROLE, migrações, emissão de sessões, login real, entrega de e-mails
ou Pix. Se for necessário preparar futura troca controlada do
processo visual por modo homologação, deve haver inspeção
de ownership/comando e manutenção expressamente autorizada.

Nenhuma credencial em chat, issue, commit, screenshot ou logs.
FR Caixinha 2.2 totalmente isolado.
