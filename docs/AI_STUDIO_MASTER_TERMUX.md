# AI Studio — Integracao do Administrador Master existente ao PostgreSQL local

**Repositorio unico desta tarefa:** 
fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP
PR #2, branch `atualizacao-ai-studio-9b46a63187`.

O outro repositorio e OUTRO aplicativo. Nao compartilhar cluster, banco, conta tecnica, segredos ou backups.

## Decisao de arquitetura: NAO criar outro painel Master

O frontend ja possui Painel Master (SaaS), Licencas e Precos, Suporte e Auditoria.
A API ja possui papel MASTER, `require_master` e rotas `/api/v1/master`.
O cadastro inicial existente e `backend/scripts/bootstrap_master.py`.
O novo `backend/scripts/bootstrap_aistudio_master.py` APENAS protege o uso local do bootstrap existente; nao cria outra identidade, tela ou perfil.

A identidade e unica, com contextos MASTER, TENANT_ADMIN e TENANT_MEMBER.
O MASTER administra licencas, plataforma e indicadores agregados; nao herda acesso a contas, extratos nem operacoes financeiras dos tenants.
O contexto de membro/admin de uma caixinha exige vinculo ativo e troca explicita.
MASTER do aplicativo NAO e PostgreSQL SUPERUSER.

## Estado verificado em 01/11/2026 pelo operador

- Git checkout em `~/frcaixinha-aistudio-mobile`, branch da PR #2.
- Cluster PostgreSQL 18.6: `$PREFIX/var/lib/frcaixinha_aistudio_pg18`, escutando apenas `127.0.0.1:5433`.
- Banco vazio `frcaixinha_aistudio_dev`, de propriedade de `frc_ai_owner`.
- Usuarios de LOGIN `frc_ai_app` e `frc_ai_auth` criados, sem SUPERUSER ou BYPASSRLS, e senhas definidas localmente.
- Debian PRoot: ambiente virtual `/root/.venvs/frcaixinha-aistudio` com FastAPI, Uvicorn, asyncpg e psycopg importados com sucesso.
- **As migracoes AINDA NAO foram executadas no celular, e nenhuma conta Master foi provisionada.**

## Sincronizacao segura para a nova branch

No Termux (nao precisa entrar em Debian):

```bash
cd ~/frcaixinha-aistudio-mobile || exit 1
git status --short --branch
git fetch origin
git merge --ff-only origin/atualizacao-ai-studio-9b46a63187
git log -1 --oneline
```

Se houver conflito ou alteracoes locais, nao usar reset/clean/force. Parar e conferir.

## Inspecao de seguranca — SOMENTE LEITURA

```bash
cd ~/frcaixinha-aistudio-mobile || exit 1
bash backend/scripts/aistudio_db_local.sh check
```

Pede senha de `frc_ai_owner`. Este modo nao aplica SQL de escrita.

## Execucao futura das migracoes — SOMENTE COM AUTORIZACAO ESPECIFICA

O script abaixo esta **preparado, mas NAO deve ser executado durante a simples sincronizacao**.
A autorizacao para escrever codigos no GitHub NAO equivale a autorizacao para modificar o banco no celular.

Apos revisar a sequencia, backup, versoes e obter autorizacao expressa:

```bash
cd ~/frcaixinha-aistudio-mobile || exit 1
AI_STUDIO_APPLY_MIGRATIONS=YES bash backend/scripts/aistudio_db_local.sh apply
```

Exige confirmacao digitada `MIGRAR_SOMENTE_AI_STUDIO`; confirma repo/branch/PGDATA/porta/owner/versao/banco vazio/papeis; usa `psql --single-transaction` e migra SQL `001` ate `010` sem alterar os arquivos legados.
Na MESMA transacao vincula `frc_ai_app` ao papel `frcaixinha_app_role` e `frc_ai_auth` ao papel `frcaixinha_auth_role`; falhas causam rollback.
Nao cria usuarios humanos nem disponibiliza transacoes bancarias reais.

Apos execucao autorizada, verificar:

```bash
bash backend/scripts/aistudio_db_local.sh verify
```

O modo `verify` exige que `public.users` exista; antes das migracoes, use `check`.

## Provisionamento do PRIMEIRO Master — FUTURO, NAO EXECUTAR AGORA

Depois de migrar e validar RLS, e mediante autorizacao especifica, usar apenas a ferramenta de homologacao local, sem imprimir as credenciais e sem recriar a interface:

```bash
proot-distro login debian -- /bin/bash -lc '
cd /data/data/com.termux/files/home/frcaixinha-aistudio-mobile || exit 1
AI_STUDIO_ALLOW_MASTER_BOOTSTRAP=YES \
  /root/.venvs/frcaixinha-aistudio/bin/python \
  backend/scripts/bootstrap_aistudio_master.py
'
```

A ferramenta exige a palavra `PROVISIONAR_MASTER_AI_STUDIO`, confirma senha do administrador somente via terminal e valida a identidade REAL da conexao PostgreSQL:
usuario `frc_ai_owner`, banco `frcaixinha_aistudio_dev`, porta 5433,
PGDATA dedicado. Antes de cadastrar, exige tabelas de identidade/auditoria
e verifica que nao existe Master. Solicita dados e senha no terminal (nao no chat),
gera segredo de inicializacao em memoria e chama o `bootstrap_master.py` JA EXISTENTE.

Nao usar `frc_ai_app` nem `frc_ai_auth` para bootstrap, pois nao devem ter poderes de gravacao sobre credenciais e audit_events.

## Integracao FastAPI — etapa seguinte

O arquivo privado de variaveis continua em
`/root/.config/frcaixinha-aistudio-mobile/api.env` dentro do Debian PRoot,
permissao `600`; nunca versionar.
Usar `DATABASE_URL` com `frc_ai_app` e `AUTH_DATABASE_URL` com `frc_ai_auth`,
ambas no banco AI Studio `127.0.0.1:5433/frcaixinha_aistudio_dev`.
O script `backend/scripts/run_termux_fastapi.sh` bloqueia URLs divergentes.
`FRCAIXINHA_TEST_AUTH=1` somente em homologacao e nao em producao.
Validar `/api/health`, `/api/health/ready`, login, sessao, troca de contexto,
e autorizacoes negadas entre tenants antes de usar APK.

**Nao baixar/instalar APK nem habilitar Pix/emprestimos/boloes/rifas reais antes de testes e autorizacoes especificas.**
