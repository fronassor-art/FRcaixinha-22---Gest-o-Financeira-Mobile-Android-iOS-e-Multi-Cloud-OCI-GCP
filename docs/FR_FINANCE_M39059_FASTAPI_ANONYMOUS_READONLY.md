# FR Finance M39059 — API existente, readiness e acesso anônimo (somente leitura)

## Pré-condições validadas
M39058 no Termux: 25/25 testes PASS e as contas frc_ai_app,
frc_ai_auth e frc_ai_verifier autenticaram e passaram nos controles
de permissões no FR Finance PG18.6, 127.0.0.1:5433.
Nenhuma senha foi alterada.

## Objetivo
Provar que o serviço já existente em 127.0.0.1:8000:
1. apresenta /api/health como FR Finance;
2. declara corretamente /api/v1/auth/status no modo TEST_MODE;
3. nega 401 sem token em /api/v1/auth/me e na rota de capacidade de crédito;
4. responde ao preflight CORS do WebView Android Origin http://localhost;
5. passa /api/health/ready, que lê as três conexões técnicas e o esquema
   de homologação e devolve READY_FOR_TEST_AUTH/LOCAL_HOMOLOGATION_ONLY.

Não executa POST /login, não cria sessão, não invoca o APK, não cria
servidor novo, não conecta à porta 5432, não altera banco ou arquivo privado,
não envia SMTP/Pix, não desbloqueia produção.

Requisições limitadas a cinco URLs fixas no loopback:8000, somente GET/OPTIONS,
sem proxy, cookie, cabeçalho de autenticação ou redirecionamentos.
O resultado mostra somente códigos de estado e etiquetas, nunca dados de usuário,
segredos ou corpo das respostas.

## Executar no Termux nativo

    cd "$HOME/fr-finance"
    test -z "$(git status --porcelain --untracked-files=all)"
    git fetch --no-tags origin atualizacao-ai-studio-9b46a63187
    # Conferir SHA remoto e sincronizar exclusivamente por fast-forward.
    git merge --ff-only FETCH_HEAD
    AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)" PYTHONDONTWRITEBYTECODE=1 \
      python3 -B -m backend.scripts.frfinance_m39059_existing_fastapi_anonymous_readonly

## Interpretação
- PASS_LOCAL_TEST_READINESS: serviço existente identificado, pronto somente
  para testes autorizados, duas rotas privadas negam 401 e CORS correto.
- BLOCKED_FASTAPI_NOT_IDENTIFIED: processo ausente/errado em 8000. Não matar,
  reiniciar nem substituir antes de inspeção de processo.
- BLOCKED_API_CONFIGURATION_OR_GUARDS: conferir flags/DSNs já carregados no
  processo existente; não reiniciar cegamente.
- HTTP_503_NOT_READY: autenticação local ainda não pronta, mesmo que
  as três credenciais privadas em disco estejam válidas.
- TEST_MODE não significa login real autorizado nem liberação de pagamentos.

## Segurança
Toda CI usa respostas HTTP simuladas; só o Termux pode atestar o processo
original em execução. Pix real OFF, e-mails reais OFF, ativação real OFF,
nenhuma migração ou sessão.
