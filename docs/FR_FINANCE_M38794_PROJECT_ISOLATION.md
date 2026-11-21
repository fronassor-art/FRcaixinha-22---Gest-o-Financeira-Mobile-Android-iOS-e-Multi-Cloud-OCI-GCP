# FR Finance M38794 — Identidade de projeto e proteção contra acesso ao FR Caixinha 2.2

## Por que houve dúvida sobre o servidor?

A marca comercial atual é **FR Finance**, mas a evolução técnica mantém a origem no projeto **AI Studio / FRcaixinha-22**. O nome histórico do cluster `frcaixinha_aistudio_pg18` pertence ao FR Finance, não ao repositório FR Caixinha 2.2. O script `backend/scripts/run_termux_fastapi.sh` já proíbe usar credenciais e clusters do projeto independente 2.2.

A sugestão anterior de executar `pg_ctl` para iniciar o PostgreSQL original estava baseada em scripts históricos do projeto AI Studio, mas foi feita **antes de uma verificação local do worktree, remoto e identidade do cluster em execução**. Nenhum teste GitHub Actions substitui essa verificação no aparelho. Até o preflight local, a recomendação operacional é **não iniciar nem migrar qualquer cluster**.

## Identificações documentadas (não são prova de serviço ativo)

| Propriedade | FR Finance — atual | FR Caixinha 2.2 — não usar |
|---|---|---|
| Repositório | `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP` | `fronassor-art/FRcaixinha-2.2` |
| Raiz Termux | `$HOME/fr-finance` | `$HOME/FRcaixinha_2.2` |
| Banco | `frcaixinha_aistudio_dev` | `frcaixinha_2_2_dev` |
| Porta | `5433` | `5432` |
| Dono de banco | `frc_ai_owner` | `frc22_owner` |
| Diretório `$PREFIX/var/lib` | `frcaixinha_aistudio_pg18` | `frcaixinha_2_2_pg18` |

O arquivo `backend/config/frfinance_project_identity.json` documenta os valores e é conferido pelo programa M38794, que contém constantes imutáveis independentes do JSON. A aplicação antiga 2.2 não é alterada por este pacote.

## Comandos somente leitura

No Termux, dentro do repositório FR Finance:

    cd "$HOME/fr-finance"
    python backend/scripts/frfinance_m38794_project_isolation.py reference
    python backend/scripts/frfinance_m38794_project_isolation.py inspect

O comando `reference` só compara o manifesto com a configuração esperada no código (inclusive em CI). O comando `inspect` verifica que o script roda em `$HOME/fr-finance`, que o `origin` GitHub é o repositório correto, que a branch é a branch AI Studio, e que o diretório de dados tem PostgreSQL 18. Quando existir `postmaster.pid`, só verifica as informações escritas de diretório e porta. Ele **não comprova que o processo está rodando**.

A função `inspect` faz apenas leitura de arquivos locais e invoca comandos Git que só leem repositório. Não executa `pg_ctl`, `pg_isready`, `psql`, socket, SQL, migrações, backups, `initdb` nem configuração OCI. Se houver caminho divergente, symlink de PGDATA, versão incorreta, remoto diferente ou pidfile com porta 5432, retorna `BLOCKED`.

`M38794_PROJECT_SEPARATION=PASS_STATIC` confirma apenas a separação dos artefatos e metadados presentes no dispositivo. `M38794_LIVE_SERVER_IDENTITY=NOT_ATTESTED` é intencional: antes de conectar, não é possível provar qual processo atende uma porta. Mesmo após a inspeção, **não iniciar PostgreSQL automaticamente**. Para comprovar a identidade operacional seria preciso um protocolo separado e aprovado, com identificação de cluster por servidor/porta/usuário/banco, sem alterações.

## Regras de segurança

- Nunca iniciar, parar ou conectar no PostgreSQL 2.2 como se fosse o FR Finance.
- Nunca assumir que o nome do projeto comercial redefine automaticamente o caminho físico de um cluster PostgreSQL.
- Nunca fazer alterações de PGDATA, migrações, senha, papéis, arquivos de controle ou `postmaster.pid` por este preflight.
- O erro prévio `M38792_FAILURE_CLASS=CONNECTION_REFUSED` é apenas recusa da conexão 127.0.0.1:5433 no momento da consulta; não prova problema na senha ou nas migrações.
- O script histórico `backend/scripts/aistudio_local_parity_034_041.sh` ainda menciona o worktree anterior `$HOME/frcaixinha-aistudio-mobile`; **não invocá-lo para migrações no FR Finance renomeado**, sem reconciliação separada de ambiente e autorização.
- Regressões de CI e Termux são homologação offline; OCI, SMTP, Pix, pagamentos e ativação real continuam desativados; produção bloqueada.

## Entregas versionadas

- `backend/config/frfinance_project_identity.json`: manifesto de dupla identidade segregada.
- `backend/scripts/frfinance_m38794_project_isolation.py`: preflight sem rede/banco.
- `backend/tests/test_m38794_project_isolation_ci.py`: casos positivos e bloqueios cruzados.
- `.github/workflows/frfinance-m38794-project-isolation-ci.yml`: testes sem PostgreSQL real.
