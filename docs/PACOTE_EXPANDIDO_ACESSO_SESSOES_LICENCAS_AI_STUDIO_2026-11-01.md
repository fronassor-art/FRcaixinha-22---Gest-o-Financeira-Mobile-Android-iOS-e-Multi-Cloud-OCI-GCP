# AI Studio — Pacote ampliado de acesso único, sessões e licenças

**Data:** 2026-11-01. **Repositório:** aplicativo Google AI Studio,
branch `atualizacao-ai-studio-9b46a63187`, PR #2 em rascunho.
Checkpoint Termux confirmado antes desta rodada: `c4982e9`.

## Objetivo

Integrar funcionalidade real de HOMOLOGAÇÃO para contas que participam de várias
caixinhas, sem copiar pessoas nem ampliar privilégios, além de melhorar a
resposta à revogação de sessões e evitar que licenças vencidas apareçam ativas.
A camada de faturamento/convite reais permanece BLOQUEADA.

## Entregas deste pacote (12 frentes coordenadas)

1. **Migração 019, ainda não aplicada localmente:** função SQL
   `auth_active_membership_contexts(uuid)` retorna `tenant_id`, papel e
   `tenant_name` apenas quando usuário, tenant e vínculo estão ativos.
   Executável somente pelo papel de autenticação; não libera SELECT geral em
   `tenants`, `memberships` ou acesso à tabela `sessions` pelo app.
2. **Nomes oficiais no seletor:** `GET /api/v1/auth/contexts` usa a
   função e retorna `tenant_name`. O frontend mostra nome real no
   lugar de um identificador opaco; permanece um único usuário e múltiplos
   papéis explícitos. Master sem caixinha sempre aparece como plataforma.
3. **Validação do contrato TypeScript:** nomes opcionais não podem ser
   vazios, conter controles ou ultrapassar o tamanho do banco. O HTML
   continua escapado pelo React.
4. **Inventário de sessões:** `GET /api/v1/auth/sessions` retorna
   somente id de sessão, papel, tenant, criação, expiração e flag
   `current`; nunca expõe token/hash, IP, dispositivo ou credencial.
5. **Revogação individual:** `POST /api/v1/auth/sessions/{id}/revoke`
   só atua se a sessão pertence à própria pessoa e ainda está ativa.
   Não aceita `user_id` arbitrário do frontend; sessão de outra pessoa
   recebe 404.
6. **Painel de segurança pessoal:** componente React lista as próprias
   sessões e oferece encerramento específico. Revogar a sessão atual
   invalida imediatamente o login local; a resposta do servidor é
   verificada.
7. **Estado efetivo da licença:** consultas Master e administrador incluem
   `effective_status` computado pelo PostgreSQL; `ACTIVE` vencida
   torna-se `EXPIRED` na resposta independentemente de job agendado,
   sem reescrever o histórico.
8. **Master SaaS no frontend:** exibe a contagem e o status
   **efetivo**, sem considerar como ativa uma licença vencida.
9. **Suspensão controlada em CI:** Master ativo pode suspender licença
   não vencida apenas com justificativa, em transação auditável. Membro
   e administrador de tenant não podem suspender por esta interface.
10. **Retomada controlada em CI:** não renova o prazo, só restaura
    status de `SUSPENDED` se tenant ativo, licença não vencida e
    pagamento continuar aprovado após consulta autenticada ao provedor.
    Licença revogada/expirada e pagamento estornado não são reativados.
11. **Expiração e estorno:** suspensão não impede expiração na data exata.
    Estorno integral verificado revoga também licença suspensa.
12. **Testes end-to-end sintéticos:** duas caixinhas com nomes distintos,
    outra caixinha inacessível, múltiplas sessões da mesma pessoa,
    tentativa de revogar sessão alheia, revogação atual, RLS, leitura
    do vencimento, suspensão, retomada, estorno e bloqueio fora do CI.

## Escopo proibido, preservado

- **Nenhuma migração no Termux**, PostgreSQL 18.6 `frcaixinha_aistudio_dev`
  na porta 5433 ainda com zero tabelas conforme último relatório do usuário.
  A sequência passou de 001–018 a **001–019 somente nos arquivos** e
  nos bancos descartáveis PostgreSQL 16 e 18 do GitHub Actions.
- Não provisionar Administrador Master, criar conta real, enviar convites,
  acessar contas Mercado Pago reais, ativar licença paga, gerar Pix ou
  instalar APK só porque o CI passou.
- O cadastro público, aceite jurídico e recuperação por e-mail continuam
  em 503/bloqueados até integração, prova de titularidade, rate-limit
  distribuído e revisão jurídica. Os executores `*_ci` não são endpoints
  de produção.
- Não alterar a divisão patrimonial nem os dados financeiros de tenants
  ao consultar o catálogo comercial da plataforma.
- Não mesclar a PR #2 na `main` sem aprovação posterior.

## Evidências e critérios de aceitação

- `backend/tests/test_aistudio_named_sessions_ci.py`: tenta acesso
  cruzado entre 3 tenants, sessão alheia e revogação de 2 sessões da
  própria identidade, sem token ou IP no JSON.
- `backend/tests/test_aistudio_live_engines_ci.py`: ciclo
  `ACTIVE → SUSPENDED → ACTIVE` com confirmação de pagamento, seguido
  de `REVOKED` por estorno; suspensão expira na data de corte.
- `backend/tests/test_aistudio_live_status_api.py`: retorno de
  `effective_status=EXPIRED` mesmo com status armazenado ACTIVE;
  confirma que a query SQL calcula a expiração em tempo de leitura.
- `src/tests/auth_context_security.test.ts`: nomes, papéis,
  sessões, revogação individual e concorrência de login/logout.
- `backend/tests/test_aistudio_pg18_preflight.py`: a função só
  pode ser executada pelo serviço de autenticação, não pelo financeiro.
- Five GitHub Actions jobs: frontend, FastAPI sem DB,
  PostgreSQL 16 RLS, PostgreSQL 18 preflight e APK debug.
  **Aprovação depende da conclusão real dos cinco.**

## Pendências para produção

Verificação de e-mail, assinatura de contratos, envio de convites,
auditoria jurídica, controle de preço/conta do provedor, webhook/GET
autenticado, renovação por pagamento real e publicação/instalação do APK.
A ativação e suspensão de SaaS reais dependem de autorização expressa e
de serviço operacional segregado com secrets manager.
