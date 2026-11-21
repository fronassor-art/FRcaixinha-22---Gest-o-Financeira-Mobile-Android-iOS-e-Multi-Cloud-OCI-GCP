#!/usr/bin/env bash
# Exclusivo FRcaixinha AI Studio — diagnóstico somente leitura no Termux.
set -euo pipefail
umask 077
BRANCH='atualizacao-ai-studio-9b46a63187'
ROOT="$HOME/frcaixinha-aistudio-mobile"
EXPECTED="${1:-}"
if [[ ! "$EXPECTED" =~ ^[a-f0-9]{40}$ ]]; then
  echo 'BLOQUEADO: forneça SHA completo do commit do pacote.' >&2
  exit 2
fi
command -v git >/dev/null || { echo 'BLOQUEADO: git ausente'; exit 2; }
cd "$ROOT"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || {
  echo 'BLOQUEADO: branch não é AI Studio';exit 2;
}
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo 'BLOQUEADO: arquivos locais rastreados modificados';exit 2;
}
[[ "$(git rev-parse HEAD)" == "$EXPECTED" ]] || {
  echo 'BLOQUEADO: commit local divergente';exit 2;
}
[[ "$(git rev-parse "origin/$BRANCH")" == "$EXPECTED" ]] || {
  echo 'BLOQUEADO: ref remota local divergente; não houve atualização automática';exit 2;
}
echo 'AI_STUDIO_M220_GIT_LOCAL=PASS'
command -v pg_isready >/dev/null || {
  echo 'AI_STUDIO_M220_PG5433=BLOCKED (ferramenta ausente)';exit 2;
}
pg_isready -q -h 127.0.0.1 -p 5433 || {
  echo 'AI_STUDIO_M220_PG5433=BLOCKED (porta indisponível)';exit 2;
}
echo 'AI_STUDIO_M220_PG5433=PASS (porta apenas; roles não comprovadas)'
command -v curl >/dev/null || {
  echo 'AI_STUDIO_M220_FASTAPI=BLOCKED (curl ausente)';exit 2;
}
health="$(curl --silent --max-time 8 --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8000/api/health || true)"
ready="$(curl --silent --max-time 8 --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8000/api/health/ready || true)"
[[ "$health" == '200' ]] || {
  echo "AI_STUDIO_M220_FASTAPI=BLOCKED (health HTTP $health)";exit 2;
}
[[ "$ready" == '200' ]] || {
  echo "AI_STUDIO_M220_READY=BLOCKED (ready HTTP $ready)";exit 2;
}
echo 'AI_STUDIO_M220_FASTAPI=PASS'
echo 'AI_STUDIO_M220_READY=PASS (HTTP apenas, não é auditoria de banco)'
echo 'AI_STUDIO_M220_BACKUP_RESTORE_OPERACIONAL=PENDENTE'
echo 'AI_STUDIO_M220_BANCO_MODIFICADO=NAO'
echo 'AI_STUDIO_M220_CHECKPOINT_READONLY=PASS'
