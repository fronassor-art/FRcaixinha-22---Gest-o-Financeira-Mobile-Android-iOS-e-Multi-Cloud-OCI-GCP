# FR Finance — M39062: alternativa segura à inspeção de TCP bloqueada pelo Android

## Evidências já comprovadas pelo Termux
- M39058: as três credenciais e respectivas permissões no PostgreSQL
  exclusivo FR Finance 18.6/5433 passaram; sem alterações em banco.
- M39059: a API FR Finance na porta 8000 funciona e nega GET anônimo
  às rotas privadas com HTTP 401; CORS Android PASS.
- M39060: as três URLs de autenticação já estão no api.env privado e as
  flags de homologação são válidas, mas o processo FastAPI está com
  DATABASE_URL não configurado e devolve BLOCKED_PENDING_CONFIG.
- M39061: 12 testes PASS, porém /proc/net/tcp está restrito pelo Android
  e o processo dono da porta 8000 não pôde ser identificado.

## Por que a M39062 existe
O script frfinance_m39051_local_apk_api.py no modo --serve limpa
DATABASE_URL, AUTH_DATABASE_URL e AUTH_VERIFIER_DATABASE_URL na memória,
com finalidade de prévia do APK sem autenticação.

M39062 tenta identificar **candidatos** a processos FastAPI do próprio
UID Termux pela sua linha de comando, sem usar /proc/net/tcp.

### Regras de segurança
- Primeiro exige Git, worktree, branch e SHA corretos no Termux nativo.
- Confere o serviço FR Finance já online via GET /api/health, loopback 8000.
- Varre apenas diretórios numéricos do /proc e apenas processos do
  mesmo UID, lendo no máximo 8 KiB do cmdline de cada um.
- Não mostra PID, argv, cmdline, env, segredos, mensagens de exceção
  ou qualquer informação sobre processos que não sejam candidatos.
- Uma única correspondência significa CANDIDATO ÚNICO, **NÃO** prova
  propriedade do socket. NÃO autoriza encerramento automático.
- Se Android restringir também essa leitura, classifica como
  ANDROID_PROC_*_RESTRICTED, sem tentar contornar permissões.
- Não faz kill, restart, deploy, SQL, migração, sessão, Pix, login real
  ou mudança no api.env.

## Classes possíveis
- M39051_VISUAL_APK: existe candidato ao modo visual do APK sem banco.
- UVICORN_DIRECT_OR_LAUNCHER: existe candidato com Uvicorn e app.main:app;
  ainda não sabemos quais variáveis o processo recebeu.
- MULTIPLE_LAUNCHER_CANDIDATES: o algoritmo não escolhe arbitrariamente.
- NONE_IDENTIFIED: processo não encontrado / comando irreconhecível.
- ANDROID_PROC_LIST_RESTRICTED ou ANDROID_PROC_COMMANDS_RESTRICTED:
  Android impediu a inspeção.

## Como usar — Termux nativo
    cd "$HOME/fr-finance"
    test -z "$(git status --porcelain --untracked-files=all)"
    git fetch --no-tags origin atualizacao-ai-studio-9b46a63187
    # Conferir a revisão aprovada antes do fast-forward.
    git merge --ff-only FETCH_HEAD
    AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)" PYTHONDONTWRITEBYTECODE=1 \
      python3 -B -m backend.scripts.frfinance_m39062_same_uid_launcher_inventory

## Etapa posterior (AINDA NÃO EXECUTADA)
Caso seja reconhecido candidato visual, o operador deverá localizar
a sessão Termux que o iniciou. Uma troca posterior para o modo
homologation requer autorização expressa e parada normal somente
daquela instância, após identificação segura.

Jamais matar processos por heurística, executar pkill/python/uvicorn
genérico, tocar no PostgreSQL ou ativar Pix real para forçar
readiness. A troca operacional não faz parte deste diagnóstico.
