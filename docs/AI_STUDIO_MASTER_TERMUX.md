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

Exige confirmacao digitada `MIGRAR_SOMENTE_AI_STUDIO`; confirma repo/branch/PGDATA/porta/owner/versao/banco vazio/papeis; usa `psql --single-transaction` e migra SQL `001` ate `014` sem alterar os arquivos legados.
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

## Evolucao dos motores por perfil — fase de consultas e catalogo (GitHub)

No mesmo repositorio AI Studio, foram integradas:
- Painel MASTER: leitura de caixinhas cadastradas via `/api/v1/master/overview`, sem acesso ao patrimonio dos tenants.
- Precos MASTER: `011_platform_license_catalog.sql` cria catalogo e historico de precos SaaS; `/api/v1/master/licenses` le dados persistidos, `POST /api/v1/master/license-prices` anexa versao imutavel com registro na auditoria. Nao registra assinatura paga nem autoriza cobranca.
- Painel TENANT_ADMIN / TENANT_MEMBER: `GET /api/v1/tenants/{tenant_id}/dashboard` consulta contagens autorizadas por RLS.
- Lista de membros: `GET /api/v1/tenants/{tenant_id}/members`, exclusiva do ADMIN do tenant, sem CPF/telefone.
- Livro-razao e emprestimos: telas autenticadas consultam a API; simulacao Price e somente matematica, nunca liberacao ou quitação.
- Contribuicoes: tela existente consulta API e nao confirma Pix sem reconciliacao.

O guard local agora exige que `011` seja incluida **na mesma transacao** de `001-010` para banco ainda vazio. Por isso, uma migracao ja autorizada anteriormente para apenas 001-010 **nao se estende automaticamente** a esta versao. Apos sync, verificar diff e solicitar consentimento especifico para 001-018 antes de rodar `apply`. Este documento nao constitui comando de execucao.

### Pendencias que nao devem ser apresentadas como prontas
- Contratacao, renovacao, suspensao e cobranca SaaS; historico de preco nao equivale a receita.
- Aceite e envio de convites; assinaturas anuais de autoemprestimo.
- Pix, OAuth, webhooks, conciliacao e transferencias reais.
- Ledger autoritativo e fechamento com pagamentos reais.
- Monitoramento e failover Multi-Cloud reais; rifa e bolao somente demonstrativos.
- Teste real no Android: o GitHub Actions compila o APK, mas nao testa a integracao no aparelho.

O operador deve sincronizar os arquivos pelo git antes de prosseguir, sem restaurar seed como dados financeiros reais. O PostgreSQL local permanece sem migracoes ate nova autorizacao.


## Ajustes P0 subsequentes: politica Price e privacidade no papel de aplicacao

- `/api/v1/tenants/{tenant_id}/loans/simulate` agora e **somente leitura** e exige
  ciclo `ABERTO` + politica `ACTIVE` acessivel por RLS e pertencente ao mesmo tenant.
  A taxa e o prazo maximo sao exclusivamente os da politica, nunca do cliente.
  Se o cliente enviar `monthly_rate`, retorna HTTP 422. Sem ciclo/politica: 409.
  O calculo usa o calendario do ciclo em vez de presumir 2027.
- O calculo Price puro continua disponivel em testes, nao libera nenhum valor.
- A migracao adicional `012_minimize_application_identity_access.sql` retira do
  papel app leitura geral de `public.users` e concede somente `(id,full_name)`.
  A conta de autenticacao conserva papeis separados; hashes e CPF ficam fora
  do papel de aplicacao. Isto NAO cria RLS em users e nao substitui
  protecao contra consultas cross-tenant nos endpoints.
- `store.ts`: login autenticado nao pode registrar localmente alteracao de
  preco ou inicio/revogacao de suporte ficticios.
- Testes FastAPI e GitHub Actions executam os novos cenarios em banco descartavel,
  incluindo matriz de permissao por usuario e tenant.

**O banco `frcaixinha_aistudio_dev` do Termux permanece com zero tabelas.
Nao executar `apply`, `verify` nem bootstrap sem nova autorizacao do proprietario.**


## Preparacao adicional P0 — Privacidade de usuarios (SEM MIGRAR AGORA)

- A migration `013_users_identity_rls.sql` habilita `ENABLE/FORCE ROW LEVEL SECURITY` em `public.users`.
- Login pelo papel `frcaixinha_auth_role` mantem SELECT das colunas explicitamente autorizadas. O papel financeiro `frcaixinha_app_role` ve somente `id,full_name` dos membros ativos da propria caixinha no contexto TENANT_ADMIN, ou o proprio registro nos papeis validados.
- Master tem acesso apenas ao proprio registro nessa tabela; seu inventario SaaS continua na tabela tenants, sem saldos financeiros.
- Teste em PostgreSQL 16 descartavel exige que Admin A nao veja nomes de B, membro veja apenas o proprio nome, MASTER apenas o proprio, sem contexto zero linhas.
- Nao executar as migracoes locais. O script `apply` segue explicitamente bloqueado ate nova autorizacao e agora compreende `001-018`.


## Preparação 014 (pacote multitarefa) — executar APENAS no CI descartável

A migração `014_account_lifecycle_preparation.sql` prepara o estado do
convite (entrega simulada no CI, aceite único, revogação, expiração) e a
tabela `password_reset_tokens` para recuperação de senha com tokens
hash SHA-256. Nenhuma função de laboratório CI foi exposta pela API.

O script de migrações locais foi atualizado para exigir `001-018`,
mas **o usuário pediu expressamente não executar migrações**.
Não usar `apply`; somente `check` para auditoria de leitura.
Consulte `docs/PACOTE_MULTITAREFA_PRE_MIGRACAO_AI_STUDIO_2026-11-01.md`.


## Novas migrações 015/016 (SOMENTE ARQUIVOS, SEM AUTORIZAÇÃO PARA APLICAR)

- 015: `contract_documents` e `contract_acceptances`, versões SHA-256,
  aceite pessoal auditável, sem mutações de documento/aceite, RLS por perfil.
- 016: `saas_subscription_preparations`, preparação de assinatura com
  versão de preço e aceite, sem status ACTIVE ou cobrança real.
- Nova API `POST /auth/logout-all`: usuário autenticado revoga todas as
  próprias sessões em contextos distintos, sem afetar outros usuários.
- Consultas documentais e SaaS específicas para Master, admin e membro.
- Testes em PostgreSQL 16/18 descartáveis, sem dados reais.
- O script local contém arquivos 001–016 mas **NÃO executar `apply`**.
  Apenas `check` ou git status/fetch/merge para sincronizar código.
- Relatório: `docs/PACOTE_AMPLIADO_GOVERNANCA_AI_STUDIO_2026-11-01.md`.


## Pacote 017–018 — gateways reais preparados, banco local NÃO autorizado

- `017_saas_payment_activation.sql`: intenções Pix SaaS da plataforma,
  licenças vinculadas a pagamento aprovado, webhooks e revisão de status.
- `018_invite_email_verification.sql`: identidade única e verificação de
  titularidade do e-mail com token de uso único; nenhum email é enviado pelo CI.
- Adaptadores reais SMTP e Mercado Pago são **desligados por padrão** e
  não estão conectados a endpoints públicos de cobrança/aceite.
- CI PostgreSQL 16/18 aplica 001–018 em bancos descartáveis; Termux somente
  sincroniza os arquivos e executa `check`, nunca `apply`.
- Ver `docs/PACOTE_CONVITES_E_SAAS_REAL_PREPARADO_2026-11-01.md`.


## Revisão de robustez 017/018 — nenhuma migração nova

- Correções nos webhooks Mercado Pago com timestamp em milissegundos,
  idempotência e verificação de estorno integral.
- Convite de usuário existente precisa de consentimento e versão
  documental correspondente, registro auditável e identidade própria.
- Link SMTP com token no fragmento para reduzir exposição em logs HTTP;
  STARTTLS obrigatório no adaptador preparado.
- **Somente código e testes no GitHub**. Continua proibido executar
  `apply`, criar contas reais, enviar e-mails ou ativar pagamentos.
- Detalhes: `docs/PACOTE_ROBUSTEZ_CONVITES_SAAS_2026-11-01.md`.
