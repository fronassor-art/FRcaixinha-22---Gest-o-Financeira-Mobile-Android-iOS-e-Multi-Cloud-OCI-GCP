# FR Finance M40600 — sincronização de código segura sob /proc restrito

**Data:** 18/11/2026. **Base:** M40590 (d32b918cd3a67321d833578da67394d8e8630aad). **PR #2:** Draft. **Produção:** bloqueada.

## Origem do bloqueio no Termux

M40590 rodou o M39800 antes de buscar o GitHub. O M39800 recebeu health FR_FINANCE_ONLINE, mas M39800_PROC=ANDROID_PROC_RESTRICTED e M39800_STATUS=BLOCKED_NO_PROCESS_PROOF, retornando código 2. Como o bloco no Termux tinha set -e, git fetch e git merge --ff-only não foram executados. A mera impressão de um checkpoint não certifica sync.

## Novo controle M40600

O script native-Termux backend/scripts/frfinance_m40600_source_sync_only.py recebe dois SHAs completos de 40 hexadecimais, verifica worktree original, origin exato, branch, HEAD anterior, arquivos rastreados limpos e consulta M39800 apenas por GET local e inspeção read-only. Se M39800 provar o processo, a leitura pode prosseguir. Se retornar *exatamente* a falha conhecida Android /proc restrito com health FR_FINANCE_ONLINE, a decisão permite **somente sincronização de arquivos**; não atesta processo, versão em memória, conexões, prontidão ou uso em produção. Erros distintos bloqueiam.

A sincronização fixa FETCH_HEAD ao SHA informado, verifica ancestralidade e executa apenas fast-forward com hooks locais desabilitados. O scanner M40580 roda depois da sincronização, estaticamente, sem DB. O teste no runner GitHub verifica dez casos de política/código sem executar o script no telefone.

**Importante:** o script M40600 entra no checkout somente depois de uma sincronização inicial segura do commit que o contém. Não executar uma versão improvisada do script fora do checkout original. Um scanner estático não comprova proteção contra SQL/GUC spoofing; a exposição M40570 continua sem mitigação.

**Nenhum acesso ao PostgreSQL original :5433 ou FR Caixinha 2.2; nenhuma migração, restart FastAPI/PostgreSQL, reload, credencial, conexão com provedor, Pix ou pagamento real.** PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
