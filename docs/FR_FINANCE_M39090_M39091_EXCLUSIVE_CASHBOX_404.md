# FR Finance M39090–M39091 | Caixas exclusivos e erro 404 em Crédito Especial

## Evidência de homologação física (14/11/2026)
Capturas enviadas: o perfil `MASTER` oferece Gestão de Caixinhas/Licenças; o perfil `TENANT_ADMIN` oferece painel geral, contribuições, livro-razão, fechamento e campanhas. Nenhum exibe os dois caixas exclusivos. Em Campanhas aparece `Operação recusada pelo servidor (404)`. A UI Android apresenta o commit `fb74b4f`.

## Requisito vigente
- `docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md` seção 2: Caixa Master recebe **somente receitas SaaS da plataforma**; dinheiro e patrimônio da caixinha são segregados por tenant.
- `docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md`, seções C/D: Master não acessa contas/membros, cada administrador tem sua própria tesouraria, 15% do lucro líquido elegível da caixinha ao administrador, 85% aos membros; capital principal não é lucro.
- `backend/app/financial_cashboxes.py` mantém segregação de recebedores e prévia de 15/85 sem confirmar dinheiro, sem transferências e sem base para declarar saldo bancário.

## Entrega de software M39090 — somente leitura
1. `backend/app/routers/exclusive_cashboxes.py`: novos GETs `/api/v1/master/exclusive-cashbox` (somente Master, contagens de intenções de cobrança SaaS e preparações de assinatura sob RLS) e `/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox` (somente administrador titular, sessão vinculada ao tenant, total de registros contábeis daquele tenant). Nenhum POST, saldo, valor de comissão calculado, transferência, Pix, autorização de fechamento ou alteração financeira.
2. `src/components/ExclusiveCashboxView.tsx` mostra os dois painéis distintos com estado de carregamento, falha fechada, consulta ao servidor e **saldo não disponível** (não exibe R$ 0,00 fictício). Menus e botões no Dashboard para Master/Admin, com isolamento `roleScope`. Membro não recebe menu nem rota autorizada.
3. `src/services/exclusiveCashboxBoundary.ts` valida rigorosamente fonte, escopo, tenant, campos e flags de nenhuma conciliação, impedindo resposta falsa com saldo ou operações ativadas.
4. Testes em `backend/tests/test_m39090_exclusive_cashboxes_ci.py` simulam FastAPI/TestClient/RLS e negam Master adversário, membro, admin outro tenant e não titular antes de ler ledger. `src/tests/m39090_exclusive_cashboxes_ci.test.ts` cobre UI, perfis e parser.

**Limite explícito:** esta entrega cria interfaces e contratos de consulta com dados contábeis reais *registrados*, mas não cria contas bancárias, saldos de titularidade ou a infraestrutura de movimentação. A futura implementação de saldo do administrador requer esquema de remuneração por fechamento, identificação segura do beneficiário, conciliação confirmada, auditoria, contratos, eventuais migrações autorizadas e gates dos provedores. Contagem de documentos não é recebimento. Nem R$ 0,00 fictício deve aparecer.

## Erro 404 — M39091
- A rota exata `GET /api/v1/tenants/{tenant_id}/special-credit/capabilities` está presente em `backend/app/routers/special_credit.py` e registrada em `backend/app/main.py`. A resposta 404 é compatível com FastAPI antigo/incorreto no loopback, não prova que falta tabela no PostgreSQL. `_enabled()` bloqueia homologação financeira com 503 se flags ou identidade da base estiverem fora do sandbox, e isso nunca deve ser contornado.
- `src/services/specialCreditRequestBoundary.ts` agora explica especificamente 404 de capabilities, sem fallback, sem tentar outro banco ou ativar crédito.
- A label do botão do administrador passou a **Atualizar campanhas**.
- `backend/scripts/frfinance_m39091_api_route_probe_readonly.py`: GET anônimo **somente** `http://127.0.0.1:8000/openapi.json`, sem token, sem acesso a DB, sem reiniciar processo. Compara rotas esperadas com as rotas em execução e relata `STALE_OR_DIFFERENT_APP` ou `BACKEND_NOT_REACHABLE`. A verificação de fonte não substitui diagnóstico do processo executando.
- O 404 só estará efetivamente resolvido em aparelho quando o backend correto apresentar a rota, a configuração de sandbox for homologada e as ações retornarem os códigos/contratos corretos. Evitar afirmar que apenas uma atualização de APK corrige servidor antigo.

## Política de execução
- GitHub/CI e APK debug primeiro, com regressões. PR #2 permanece draft.
- Sincronização nativa do Termux por fast-forward **após** CI/checagem.
- Diagnóstico de API somente GET; qualquer reinício de servidor local só após examinar PID/comando/porta, mantendo PostgreSQL 18 porta 5433 e banco `frcaixinha_aistudio_dev` isolados do FR Caixinha 2.2.
- **Não executar migrações SQL locais sem validação específica e autorização nova**, não abrir serviços ou Pix reais. `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`.
