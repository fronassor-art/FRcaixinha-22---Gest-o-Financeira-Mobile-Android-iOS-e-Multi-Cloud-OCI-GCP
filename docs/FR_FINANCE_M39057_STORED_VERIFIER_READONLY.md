# FR Finance M39057 — validação da senha técnica guardada (somente leitura)

## Motivo
A M39056 confirmou o PostgreSQL 18.6 FR Finance, banco frcaixinha_aistudio_dev,
porta 5433 e diretório frcaixinha_aistudio_pg18. A role frc_ai_verifier existe e
pode conectar, mas a senha introduzida manualmente foi rejeitada.

O provisionamento histórico do FR Finance gera senha própria aleatória
para frc_ai_verifier e a inclui em AUTH_VERIFIER_DATABASE_URL, no arquivo local
privado $HOME/.config/frcaixinha-aistudio-mobile/api.env. Essa senha pode ser
diferente da senha que o operador conhece e nunca deve ser publicada.

## M39057
- Exige o worktree/branch/SHA original de FR Finance.
- Lê apenas duas URLs do arquivo privado, sem executá-lo como shell nem imprimir valores.
- Rejeita symlinks, permissões expostas, caminhos diferentes e alvos fora de
  127.0.0.1:5433/frcaixinha_aistudio_dev.
- Testa a senha técnica já guardada com UMA conexão apenas de leitura
  usando o papel frc_ai_verifier; valida identidade do banco e versão PG18.
- Não pede senha, não redefine nenhuma, não migra banco, não gera sessão,
  não ativa API, SMTP ou Pix e nunca toca na porta 5432.

## Termux nativo
Conferir primeiro branch e alterações locais:

    cd "$HOME/fr-finance"
    git branch --show-current
    git status --short

Sincronizar SOMENTE se a branch for atualizacao-ai-studio-9b46a63187 e
o status estiver limpo:

    git pull --ff-only origin atualizacao-ai-studio-9b46a63187

Rodar a auditoria sem mostrar segredos:

    AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)" python3 -m backend.scripts.frfinance_m39057_stored_verifier_readonly

## Interpretação
- M39057_STORED_VERIFIER=PASS: a senha guardada funciona. A tentativa
  manual M39056 usou uma entrada diferente ou houve divergência de digitação.
- INVALID_PASSWORD: a senha armazenada também falhou. Investigar recuperação
  e fontes de configuração antes de qualquer ALTER ROLE.
- BLOCKED_*: preservar o estado e avaliar configuração/ambiente sem mudanças.

Não executar cat/grep/printenv/set -x para mostrar credenciais. Não publicar
api.env, DATABASE_URL, AUTH_DATABASE_URL, AUTH_VERIFIER_DATABASE_URL nem hashes.
CI cobre código e cenários sintéticos; somente a execução local verifica a senha real.
