# FR Finance AI Studio — M39035–M39036: restauração do DIRETÓRIO ÚNICO

## Contrato operacional invariável

- Repositório GitHub ÚNICO: `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`.
- Branch: `atualizacao-ai-studio-9b46a63187`.
- ÚNICO checkout canônico: **Termux nativo** `/data/data/com.termux/files/home/fr-finance` (`~/fr-finance` no Termux).
- Debian é **ferramenta auxiliar** de Python/FastAPI. Usar o mesmo checkout via caminho Android acima ou bind mount `/mnt/fr-finance` **SOMENTE após comprovar identidade física com stat**. Nunca criar `/root/fr-finance` de novo.
- PostgreSQL ÚNICO: `127.0.0.1:5433/frcaixinha_aistudio_dev`, data directory `/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18`. Banco não mora na pasta Git e não deve ser movido.
- **SQL 110/111 JÁ EXECUTADAS** e atestadas no banco original em M39031/M39032. Não reaplicar nenhuma SQL; instalador M39020 legado é desabilitado.
- O backup M39030 e o pré-M39031 permanecem **privados, sem criptografia**, no Debian `/root/frfinance-backups/` FORA dos dois checkouts. Não excluir esses arquivos ao retirar a cópia paralela.
- Pix real, pagamentos e envios externos permanecem desativados.
- `~/fr-finance` dentro do Debian equivale a `/root/fr-finance`, **NÃO** à pasta nativa do Termux.
- Sempre identificar: **Execute no Termux** (Android nativo) ou **Execute no Debian** (`root@localhost`). Nunca usar “Execute no Termux; entre no Debian” para comandos ambíguos.

## Plano de recuperação com gates

1. **Inspecionar o original Termux**, sem alterar nada: identificar origin, branch, SHA, árvore rastreada/untracked e guardá-los em relatório. Nunca inventar caminhos, arquivos ou hashes.
2. **Sincronizar APENAS o original** com `git fetch` e `git merge --ff-only` da branch aprovada **se a árvore estiver limpa** e `HEAD` for ancestral do remoto. Nenhum `reset --hard`, `git clean`, `stash` automático, `clone`, `checkout -f`, `pull --rebase` nem cópia indiscriminada. Se houver alteração local, **parar** para preservar.
3. **Conferir no Debian** que o caminho Android aponta para o checkout canônico e, se `/mnt/fr-finance` existir, usar `stat -Lc '%d:%i'` para verificar a mesma pasta física. Reexecutar apenas auditorias pós-migração M39032/M39034 (read-only) pelo caminho canônico; nunca via clone.
4. **Auditar o clone redundante** `/root/fr-finance` em M39036: comparar SHA, branches, worktree, arquivos ignorados, stash e commits só locais. Arquivos ignorados incluem possíveis credenciais, artefatos/APKs ou logs. Se houver conteúdo exclusivo, preservar e reconciliar antes de excluir.
5. **Excluir o clone redundante somente após prova positiva**: SHA canônico=SHA secundário, ambos worktrees sem alterações, sem arquivos ignorados/untracked, sem stashes/commits locais, sem bind mount/symlink/serviço usando a pasta secundária, e cópias de segurança válidas. Remoção **separada**, consentida e com alvo literal exato `/root/fr-finance`; nunca usar o nome `~/fr-finance` sem especificar ambiente.
6. **Validar Android e FastAPI** só depois da unificação. A falha M39034 ocorreu APÓS RLS passar; a causa do runtime FastAPI local precisa ser diagnosticada separadamente, sem supor que o PostgreSQL falhou.

## Evidência já disponível antes da recuperação

- M39030 backup PG18 (47 tabelas): PASS, restaurado em base descartável; original preservado.
- M39031 SQL110/111 no banco oficial: PASS, atômico, 6 tabelas FORCE RLS/5 triggers.
- M39032 pós-migração: PASS, 53 tabelas, 16 policies, RLS e permissões.
- M39033 sintaxe Python e CI sintética: PASS; não prova Android E2E.
- M39034 banco sob papel `frc_ai_app`: PASS, RLS ativo 6/6 sem contexto; runtime da API local reportou `BLOCKED_RUNTIME_OR_DATABASE_CHECK` após teste PG. Não atribuir a corrupção ou indisponibilidade do PostgreSQL.
- Nada acima comprova ainda a sincronização do checkout canônico Termux; isso exige M39035 no aparelho.

## Comandos versionados

**Execute no Termux (fora do Debian)**:
```bash
cd "$HOME/fr-finance"
bash backend/scripts/frfinance_m39035_single_directory_termux.sh audit
# sync SOMENTE depois da verificação do checkout original e SHA aprovado:
FR_FINANCE_APPROVED_SHA=<sha_completo_aprovado> \
  bash backend/scripts/frfinance_m39035_single_directory_termux.sh sync
```

**Execute no Debian** (`root@localhost`), DEPOIS de sincronizar o original:
```bash
bash /data/data/com.termux/files/home/fr-finance/backend/scripts/frfinance_m39036_debian_clone_audit_only.sh
```

**Exclusão condicional, separada da sincronização, APENAS após M39036 retornar elegível:**
```bash
# Somente no Debian; requer prova de SHA, árvore limpa,
# ausência de arquivos ignorados, stashes, commits só locais,
# integridade dos DOIS backups e confirmação interativa.
FR_FINANCE_APPROVED_SHA=<sha_completo_aprovado> \\
  bash /data/data/com.termux/files/home/fr-finance/backend/scripts/frfinance_m39037_delete_verified_duplicate_debian.sh
```
Se qualquer uma dessas condições falhar, a exclusão é BLOQUEADA. Não utilizar `rm -rf` manualmente para contornar essa proteção.

**Atenção:** até a primeira sincronização, o script M39035 pode ainda não existir no original. Use a inspeção e sincronização conservadora encaminhadas ao operador no chat; NUNCA crie clone alternativo para obter o script.

A exclusão de `/root/fr-finance` é **passo futuro com prova**, nunca efeito colateral de `audit`, `sync` ou de comandos de banco.
