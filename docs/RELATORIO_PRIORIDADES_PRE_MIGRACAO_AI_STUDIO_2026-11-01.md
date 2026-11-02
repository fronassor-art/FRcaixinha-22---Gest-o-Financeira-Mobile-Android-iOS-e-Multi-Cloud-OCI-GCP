# AI Studio — Auditoria das pendencias criticas ANTES da migracao local

**Data:** 01/11/2026 | **Base auditada:** `9bcf9e1669488add243a2469b1ca2f4d71fc0aac`
**Repositorio unico:** `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`
**Branch:** `atualizacao-ai-studio-9b46a63187` (PR #2 em draft, sem merge).
**Regra expressa do proprietario:** NÃO aplicar migracoes por enquanto; nao instalar APK.
Este relatório registra verificacoes e prioridades; NAO autoriza transferencia, cobranca,
registros financeiros reais nem altera qualquer banco do celular.

## 1. Evidencia informada pelo Termux pelo operador

- `git fetch` e `merge --ff-only` bem-sucedidos; HEAD `9bcf9e1`.
- PostgreSQL 18.6 EXCLUSIVO AI Studio:
  `127.0.0.1:5433/frcaixinha_aistudio_dev`,
  PGDATA `$PREFIX/var/lib/frcaixinha_aistudio_pg18`.
- `frc_ai_owner` superusuario administrativo; `frc_ai_app` e `frc_ai_auth`
  LOGIN, sem SUPERUSER/BYPASSRLS; banco com **0 tabelas**.
- Nenhum arquivo de migracao, papel interno Master humano ou schema foi aplicado localmente.
- CI anterior no commit `9bcf9e1`: frontend, API, PostgreSQL **16**
  descartavel e APK debug: 4 PASS. Nao comprova integracao Termux 18.6.
- **PR e commit do ultimo round nao equivalem a programa inteiramente concluido.**

## 2. Recontagem das 147 clausulas: cuidado com a fotografia anterior

Em `docs/CHECKPOINT_CONTRATO_2026-11-01.md`, havia 147 linhas documentais:

| Estado no checkpoint de referencia | Quantidade |
|---|---:|
| PARCIAL | 58 |
| BLOQUEADO | 50 |
| NAO VERIFICADO | 34 |
| DIVERGENTE | 5 |
| CONCLUIDO E TESTADO | 0 |
| TOTAL | 147 |

**Estes sao valores do checkpoint ANTERIOR aos commits 96dded7 a 9bcf9e1.**
Nao se deve recalcular porcentagem ou mudar labels sem auditar individualmente
cada requisito e confrontar testes, runtime e documentos originais.
O commit 9bcf9e1 adicionou evidencia nova, mas NAO comprovou clausula integral
e nao elimina as divergencias 4.1 e 8.2.

### Mudancas comprovadas desde o checkpoint, mantendo estados conservadores

| Clausula | Evidencia nova no codigo | Estado defensavel |
|---|---|---|
| 2.1/2.3/2.8/2.9 | Mais consultas de painel segregadas por papel e tenant, API e testes com mocks | PARCIAL; falta regressao real de RLS das novas rotas |
| 3.2/3.2-A | Migracao 011: catalogo/versionamento imutavel de preco; API de leitura e escrita para MASTER; anual=10x; CI16 | PARCIAL; sem cobranca/assinatura/aceite |
| 3.3/3.4 | Catálogo de planos persistente | PARCIAL; limite de capacidade nao comprovado na criacao de membros/cotas |
| 5.3 | SupportSessionView nao declara mais sessao real sem API; endpoint break-glass permanece negado | DIVERGENTE documental, com fluxo bloqueado |
| 4.1/8.2 | `loans/simulate` ainda aceita `monthly_rate` do cliente | DIVERGENTE ate vincular validacao a politica versionada |
| 6/8/9/10 | Paineis membros, ledger e emprestimos consultam backend, mas fluxos financeiros reais permanecem incompletos | PARCIAL/BLOQUEADO conforme cada clausula |

## 3. P0 — Alta prioridade; resolver ou obter prova ANTES da migracao

| Prioridade | Problema verificado | Arquivos-chave | Criterio para aprovar |
|---|---|---|---|
| P0-A | PostgreSQL 18.6 local nao foi ensaiado; CI16 aplicava 001-011 em varias transacoes, enquanto Termux exige uma so | workflow, backend/scripts/aistudio_db_local.sh | CI com PostgreSQL 18 DESCARTAVEL, 001-011 na mesma transacao, papéis, tabelas e RLS testados |
| P0-B | A nova API de preços Master e inventario possuem mocks de API e checagem SQL parcial; falta teste positivo REAL de permissao Master com SQL RLS | backend/app/routers/master.py; migrations/011; tests | MASTER consegue consultar catalogo e criar versao auditada; ADMIN/MEMBER nao; Master sem acesso financeiro; rollback e imutabilidade testados |
| P0-C | Login e sessoes sao expressamente `FRCAIXINHA_TEST_AUTH` de homologacao; recuperacao de conta, onboarding, convite e aceite ainda nao integram fluxo real | auth.py; invitations.py; provisioning.py | Escolher trilha de homologacao segura para Master e contas sinteticas, sem abrir cadastro publico ou fingir login produtivo |
| P0-D | Simulacao Price aceita taxa fornecida pelo cliente, sem ler politica versionada do tenant; divergencias 4.1 e 8.2 | models.py LoanSimulateRequest; routers/loans.py | Endpoint refuta taxa fora da politica ativa; testes de taxa, prazo e ciclo por tenant, usuario e contexto |
| P0-E | Frontend ainda contem `SEED_*` e caminhos locais em store para funcoes nao migradas, como fechamento, consentimento e nuvem | src/services/store.ts, CycleClosingView, ConsentView, MultiCloudView | Nao exibir resultados demonstrativos como saldos reais em nenhum perfil; demonstradores claramente rotulados; componentes sem backend devem falhar fechado |
| P0-F | Antes da migracao local, falta demonstrar bootstrap de MASTER, privilegios dos usuarios tecnicos e rollback da operacao completa em PG18 | bootstrap_aistudio_master.py; postgres migration scripts | So em CI/ambiente descartavel: senha isolada, unico MASTER, nenhum acesso superuser na API, rollback completo; nenhum comando de escrita local |

### CI adicional introduzido nesta rodada

- Novo job GitHub Actions `postgres18-preflight`, com PostgreSQL 18 descartavel.
- Migra 001-011 **em unica transacao** em `frcaixinha_ci`, nunca no Termux.
- Teste `backend/tests/test_aistudio_pg18_preflight.py` valida conta tecnica sem
  superuser, leitura do catalogo so com contexto Master, nova versao de preco
  e log de auditoria na transacao, rollback e negacao para membro.
- Esta e evidencia de pre-migracao, NAO dispensa testes locais com PG18.6,
  revisao de todas as clausulas ou autorizacao do operador.

## 4. P1 — Avancar no GitHub, mantendo bloqueios legais e financeiros

1. Concluir contrato/aceite/convite e suas evidencias sem usar dados pessoais reais.
2. Revalidar autorizacao anual do autoemprestimo com assinaturas persistentes,
   revogacao e bloqueios em aprovacao, reserva e desembolso.
3. Completar SaaS: versao de oferta, assinatura, vencimento, bloqueio zero dias,
   reativacao e segregacao de receitas (sem cobranca real).
4. Fazer ciclo/quotas/contribuicoes, inadimplencia e lucro obedecerem so politica
   e banco autoritativos; reconciliar divergencias entre SQL/React/contrato.
5. Criar testes completos de Member/Admin/Master por modulo e por dois tenants,
   incluindo troca de contexto, expiracao e nao vazamento na tela.
6. Reavaliar as 34 clausulas 'NAO VERIFICADO' em lotes individualizados.
7. Revisar observabilidade, backup/restauracao isolada, notificacoes, LGPD e
   integracao OCI/GCP REAL, distinguindo claramente o demonstrador.

## 5. Bloqueios que NAO podem ser removidos por este trabalho

- Pix e Mercado Pago reais dependem de OAuth, webhooks assinados, conciliacao,
  autorizacao juridica/operacional e testes especificos.
- Rifa e bolao permanecem exclusivamente DEMONSTRATIVOS.
- Master SaaS nunca acessa saldos financeiros ou dados bancarios de tenants.
- Compilacao do APK de debug nao valida usabilidade, TLS, distribuicao nem
  autorizacao de movimentacao real.
- Nao executar `AI_STUDIO_APPLY_MIGRATIONS=YES` neste momento.
- Nao executar `bootstrap_aistudio_master.py` no celular neste momento.
- Nao reutilizar PostgreSQL, usuarios, segredos ou caminho de OUTRO projeto.

## 6. Proxima decisao tecnica apos a revisao

Somente depois de eliminar os itens P0 comprovados e reavaliar o checkpoint
contratual, apresentar um plano de migracao restrito ao banco AI Studio com
preflight, rollback e autorizacao explicita do proprietario.
O PG local deve permanecer com **zero tabelas** ate essa decisao.


## 7. Rodada P0 posterior — alteracoes propostas para CI (NAO migradas)

Este anexo complementa o checkpoint de 147 clausulas; nao altera automaticamente
a contagem original. A migracao 012 altera apenas privilegios do papel de
aplicacao e **ainda nao foi aplicada** no PostgreSQL local.

| Frente | Correcao preparada | Prova pendente ou limite |
|---|---|---|
| P0-D 4.1/8.2 | simulador Price le `policies` ACTIVE do `cycles` ABERTO no mesmo tenant via sessao RLS; recusa taxa fornecida pelo cliente, usa inicio/fim reais do ciclo e valida prazo | Testes isolados e integracao sintética em CI; aprovação de credito, reserva e liberação seguem bloqueadas |
| P0-B Privacidade | `012_minimize_application_identity_access.sql`: papel app acessa de `users` apenas `id` e `full_name`; nao CPF/email/telefone/credenciais; usuario de autenticacao separado | Testar em PG16/PG18 CI; isolamento de nomes por tenant continua dependente de consultas/RLS |
| P0-E Demonstração | métodos locais de mudança de preço e suporte nao podem confirmar registros quando há conta autenticada | Testes frontend; demonstradores de rifa e bolao preservados sem dinheiro real |
| P0-A PostgreSQL 18.6 | Ensaio inicial das migrações 001–011 passou no CI; incluir 012 na transacao e repetir ensaio | Compatibilidade de CI não equivale a permissão para modificar Termux |
| P0-C Identidade/convite | Não habilitado: autenticação continua em homologação, convite e recuperação de senha ainda retornam bloqueio | Exige implementação, testes e revisão de segurança antes do uso real |

**Regras invariáveis:** não merge na main, não usar credenciais reais no CI,
não ativar cobrança/Pix/transferência, não criar novo painel Master,
não tocar em nenhum outro projeto e **não migrar o banco do Termux**.


## 8. Investigação P0 adicional — usuários e isolamento de nomes

O acesso técnico a `public.users` estava limitado a colunas pela migração 012, mas a linha ainda era global: mesmo não podendo ler CPF/e-mail, uma consulta direta poderia listar nomes de outras caixinhas. Preparada a migração 013 para impor RLS em `users`, com política para a autenticação dedicada e outra para o ADMIN somente dos membros ativos de sua caixinha; membro e MASTER veem sua própria identidade. Testes de integração sintéticos exigem isolamento entre dois tenants. Este resultado **não equivale a homologação em produção**, nem libera onboarding real.

**Atualizar o checkpoint de 147 requisitos apenas depois de verificar testes concluídos e cada cláusula individual. Nenhuma migração local autorizada nesta rodada.**


## 9. Nova revisão do fluxo de identidade e convites (GitHub; sem migração local)

- Confirmação local: commit e65feda sincronizado; PostgreSQL exclusivo do AI Studio
  18.6 em 127.0.0.1:5433, com **zero tabelas** e sem migrações executadas.
- Convites permanecem retornando 503 (nenhum token, vínculo ou e-mail emitido),
  mas o backend passa a recusar ANTES disso tentativas de hierarquia não
  autorizadas: membro não convida; administrador somente membro da própria
  caixinha; Master somente administradores. Sem permissão implícita por
  identidade com múltiplos papéis: vale o papel ativo da sessão.
- Login em ambiente de homologação não revela que uma conta ativa sem
  vínculo existe: HTTP 401 genérico, a tentativa conta para rate limit,
  e nenhuma sessão é criada. Testes com PostgreSQL descartável.
- **P0 ainda aberto:** token criptográfico de convite, destinatário,
  aceite transacional, expiração/revogação, prova de titularidade do e-mail,
  recuperação de senha e rate limit distribuído. Nenhuma destas funções
  está liberada para cadastro público.
- A implementação do Caderno Mestre do Master SaaS não será duplicada.
  A migração 013 permanece apenas versionada; o dono não autorizou
  nenhuma alteração no banco local.
