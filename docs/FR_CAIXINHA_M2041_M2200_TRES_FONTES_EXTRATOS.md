# FR Caixinha AI Studio — M2041–M2200 (160 controles)

**Data do pacote:** 04/11/2026. **Base homologada:** `cfea6ba8b810a4575c7dfe862817e69a699daa52` (M2040). Branch: `atualizacao-ai-studio-9b46a63187`. PR #2 deve permanecer **Draft**, sem merge. Projeto exclusivamente AI Studio, não o FRcaixinha 2.2 independente.

## Alterações efetivamente implementadas

- `backend/app/financial_three_source_preflight.py`: cruzamento de *quatro objetos de laboratório* correspondentes a três frentes de evidência: cobrança esperada, GET sintético, demonstrativo de liquidação sintético e plano de partidas dobradas sintético. Rejeita status fora de aprovado, collector, tenant, IDs, referências, valores, fonte documental e timestamps divergentes. Calcula bruto, tarifa e líquido sem ponto flutuante, conservando centavos.
- `backend/tests/test_m2200_three_source_preflight_ci.py`: cenários parametrizados de exatidão, taxas, divergências, status pendentes/estornados, três caixas, duplicações e lacunas. Executar na CI antes de qualquer declaração PASS.
- `backend/app/main.py`: health interno `GET /api/health/features/m2200`, flags de bloqueio explícitas e nenhum dado sensível.
- `src/services/ledgerJournalCursorNavigation.ts`: avançar somente quando página válida, `has_more=true`, cursor de tamanho restrito e não reutilizado; protege contra loops de cursor sem alegar snapshot bancário.
- `src/components/LedgerAccountEntries.tsx`: previne avançar com cursor inconsistente, informa o motivo e conserva controles de autenticação/tenant existentes.
- `src/tests/macropacote_360_keyset_ci.test.ts` e `src/tests/macropacote_2200_ledger_navigation_ci.test.ts`: compatibilidade e regressões de 999 avanços + 999 retornos; teste de código **não substitui homologação no APK instalado**.
- `.github/workflows/validacao-atualizacao.yml`: incorpora suites Backend e Frontend. Sem migração nova e sem alteração no PostgreSQL 5433.

## Limitações e bloqueios

**Nenhuma evidência é bancária.** As três fontes adicionais são explicitamente `SYNTHETIC_*_FIXTURE` e não autenticadas. Mesmo um encontro matemático perfeito informa apenas `SYNTHETIC_CROSS_SOURCE_MATCH_ONLY`. Não há OAuth Connect ativo, Pix, processamento de webhook de produção, lançamentos reais, capital confirmado, baixa de parcela, restituição ou autorização de fechamento.

A rota de saúde não libera funções financeiras e não mostra dados de membros. O Master não ganha visão de caixa tenant. A migração 031 é CI-only e continua fora de `backend/migrations`.

## Matriz de 160 controles

Os primeiros controles classificados `COBERTURA_SINTETICA_CI` são funções ou testes locais, não integrações operacionais. Os demais `PENDENTE_OPERACIONAL` dependem de serviços externos, aprovação ou homologação no aparelho. Não confundir quantidade de casos parametrizados com quantidade de funcionalidades concluídas.

| ID | Frente | Tarefa/controle | Estado |
|---|---|---|---|
| M2041 | Fontes de prova sintética | Exigir intenção imutável de cobrança sandbox | COBERTURA_SINTETICA_CI |
| M2042 | Fontes de prova sintética | Exigir fixture de resposta GET declarada | COBERTURA_SINTETICA_CI |
| M2043 | Fontes de prova sintética | Exigir demonstrativo sintético de liquidação | COBERTURA_SINTETICA_CI |
| M2044 | Fontes de prova sintética | Exigir plano contábil fictício de partidas dobradas | COBERTURA_SINTETICA_CI |
| M2045 | Fontes de prova sintética | Identificar payment_id da fonte GET | COBERTURA_SINTETICA_CI |
| M2046 | Fontes de prova sintética | Identificar payment_id do demonstrativo | COBERTURA_SINTETICA_CI |
| M2047 | Fontes de prova sintética | Identificar payment_id do planejamento contábil | COBERTURA_SINTETICA_CI |
| M2048 | Fontes de prova sintética | Validar referências documentais únicas | COBERTURA_SINTETICA_CI |
| M2049 | Fontes de prova sintética | Preservar a origem SYNTHETIC_GET_FIXTURE | COBERTURA_SINTETICA_CI |
| M2050 | Fontes de prova sintética | Preservar a origem SYNTHETIC_SETTLEMENT_STATEMENT_FIXTURE | COBERTURA_SINTETICA_CI |
| M2051 | Fontes de prova sintética | Preservar a origem SYNTHETIC_ACCOUNTING_PLAN_FIXTURE | COBERTURA_SINTETICA_CI |
| M2052 | Fontes de prova sintética | Rejeitar GET ausente | COBERTURA_SINTETICA_CI |
| M2053 | Fontes de prova sintética | Rejeitar demonstrativo ausente | COBERTURA_SINTETICA_CI |
| M2054 | Fontes de prova sintética | Rejeitar plano contábil ausente | COBERTURA_SINTETICA_CI |
| M2055 | Fontes de prova sintética | Expor órfãos de cada fonte | COBERTURA_SINTETICA_CI |
| M2056 | Fontes de prova sintética | GET real autenticado por PSP | PENDENTE_OPERACIONAL |
| M2057 | Fontes de prova sintética | Consulta de extrato real do recebedor | PENDENTE_OPERACIONAL |
| M2058 | Fontes de prova sintética | Arquivo de settlement assinado ou autorizado | PENDENTE_OPERACIONAL |
| M2059 | Fontes de prova sintética | Vinculação com livro contábil real por transação | PENDENTE_OPERACIONAL |
| M2060 | Fontes de prova sintética | Auditoria externa independente da proveniência | PENDENTE_OPERACIONAL |
| M2061 | Centavos, taxas e divergências | Centavos inteiros, sem float | COBERTURA_SINTETICA_CI |
| M2062 | Centavos, taxas e divergências | Valores não negativos | COBERTURA_SINTETICA_CI |
| M2063 | Centavos, taxas e divergências | Limite de centavos por registro | COBERTURA_SINTETICA_CI |
| M2064 | Centavos, taxas e divergências | Bruto maior que zero | COBERTURA_SINTETICA_CI |
| M2065 | Centavos, taxas e divergências | Tarifa não ultrapassa o bruto | COBERTURA_SINTETICA_CI |
| M2066 | Centavos, taxas e divergências | Líquido igual a bruto menos tarifa | COBERTURA_SINTETICA_CI |
| M2067 | Centavos, taxas e divergências | Contagem exata do total de obrigações | COBERTURA_SINTETICA_CI |
| M2068 | Centavos, taxas e divergências | Contagem exata do bruto conciliado fictício | COBERTURA_SINTETICA_CI |
| M2069 | Centavos, taxas e divergências | Contagem exata das taxas fictícias | COBERTURA_SINTETICA_CI |
| M2070 | Centavos, taxas e divergências | Contagem exata do líquido fictício | COBERTURA_SINTETICA_CI |
| M2071 | Centavos, taxas e divergências | Rejeição de faturas com valor divergente | COBERTURA_SINTETICA_CI |
| M2072 | Centavos, taxas e divergências | Rejeição de plano contábil sem partidas iguais | COBERTURA_SINTETICA_CI |
| M2073 | Centavos, taxas e divergências | Rejeição de consolidação acima do limite | COBERTURA_SINTETICA_CI |
| M2074 | Centavos, taxas e divergências | Teste parametrizado de 400 valores exatos | COBERTURA_SINTETICA_CI |
| M2075 | Centavos, taxas e divergências | Teste parametrizado de 301 tarifas | COBERTURA_SINTETICA_CI |
| M2076 | Centavos, taxas e divergências | Teste de desconto e taxa efetiva do provedor | PENDENTE_OPERACIONAL |
| M2077 | Centavos, taxas e divergências | Contabilização real de tarifa de adquirente | PENDENTE_OPERACIONAL |
| M2078 | Centavos, taxas e divergências | Reconciliação de saldo bancário final do ciclo | PENDENTE_OPERACIONAL |
| M2079 | Centavos, taxas e divergências | Tributação aplicável a tarifas e receitas | PENDENTE_OPERACIONAL |
| M2080 | Centavos, taxas e divergências | Estorno de taxa sobre reembolso parcial | PENDENTE_OPERACIONAL |
| M2081 | Tenants, Master e identidades | Recebedor único para cada tenant | COBERTURA_SINTETICA_CI |
| M2082 | Tenants, Master e identidades | Conta Master separada de tenant | COBERTURA_SINTETICA_CI |
| M2083 | Tenants, Master e identidades | Proibir collector compartilhado | COBERTURA_SINTETICA_CI |
| M2084 | Tenants, Master e identidades | Vincular payment_id a seu tenant | COBERTURA_SINTETICA_CI |
| M2085 | Tenants, Master e identidades | Vincular referência externa da obrigação | COBERTURA_SINTETICA_CI |
| M2086 | Tenants, Master e identidades | Rejeitar collector errado na liquidação | COBERTURA_SINTETICA_CI |
| M2087 | Tenants, Master e identidades | Rejeitar tenant diferente no plano contábil | COBERTURA_SINTETICA_CI |
| M2088 | Tenants, Master e identidades | Rejeitar provider payment_id duplicado | COBERTURA_SINTETICA_CI |
| M2089 | Tenants, Master e identidades | Rejeitar chave idempotente duplicada | COBERTURA_SINTETICA_CI |
| M2090 | Tenants, Master e identidades | Rejeitar operação duplicada | COBERTURA_SINTETICA_CI |
| M2091 | Tenants, Master e identidades | Rejeitar referência externa do mesmo caixa reutilizada | COBERTURA_SINTETICA_CI |
| M2092 | Tenants, Master e identidades | Resultado ordenado por chave de operação | COBERTURA_SINTETICA_CI |
| M2093 | Tenants, Master e identidades | Teste de três caixas independentes | COBERTURA_SINTETICA_CI |
| M2094 | Tenants, Master e identidades | OAuth real com contas financeiras segregadas | PENDENTE_OPERACIONAL |
| M2095 | Tenants, Master e identidades | Associação de sellerID ao tenant no backend | PENDENTE_OPERACIONAL |
| M2096 | Tenants, Master e identidades | Bloqueio de chaves revogadas | PENDENTE_OPERACIONAL |
| M2097 | Tenants, Master e identidades | Prova de titularidade do recebedor | PENDENTE_OPERACIONAL |
| M2098 | Tenants, Master e identidades | Rotação de credenciais em cofre | PENDENTE_OPERACIONAL |
| M2099 | Tenants, Master e identidades | Revalidação da sessão antes de registrar efeitos | PENDENTE_OPERACIONAL |
| M2100 | Tenants, Master e identidades | Revisão contábil independente por administrador | PENDENTE_OPERACIONAL |
| M2101 | Livro-Razão, extratos e cursores | Rejeitar cursor alfanumérico inválido | COBERTURA_SINTETICA_CI |
| M2102 | Livro-Razão, extratos e cursores | Rejeitar cursor excessivamente longo | COBERTURA_SINTETICA_CI |
| M2103 | Livro-Razão, extratos e cursores | Rejeitar cursor repetido | COBERTURA_SINTETICA_CI |
| M2104 | Livro-Razão, extratos e cursores | Impedir avanço além da página 1000 | COBERTURA_SINTETICA_CI |
| M2105 | Livro-Razão, extratos e cursores | Preservar acesso à página anterior | COBERTURA_SINTETICA_CI |
| M2106 | Livro-Razão, extratos e cursores | Recompor cursor ao voltar e avançar | COBERTURA_SINTETICA_CI |
| M2107 | Livro-Razão, extratos e cursores | Bloquear avanço se página não estiver pronta | COBERTURA_SINTETICA_CI |
| M2108 | Livro-Razão, extratos e cursores | Avisar inconsistência no cursor | COBERTURA_SINTETICA_CI |
| M2109 | Livro-Razão, extratos e cursores | Não apresentar saldo conciliado em consulta parcial | COBERTURA_SINTETICA_CI |
| M2110 | Livro-Razão, extratos e cursores | Rejeitar página seguinte sem has_more | COBERTURA_SINTETICA_CI |
| M2111 | Livro-Razão, extratos e cursores | Testar 999 avanços sequenciais | COBERTURA_SINTETICA_CI |
| M2112 | Livro-Razão, extratos e cursores | Testar 999 retornos sequenciais | COBERTURA_SINTETICA_CI |
| M2113 | Livro-Razão, extratos e cursores | Homologação de botão Anterior no APK | PENDENTE_OPERACIONAL |
| M2114 | Livro-Razão, extratos e cursores | Homologação de botão Próxima no APK | PENDENTE_OPERACIONAL |
| M2115 | Livro-Razão, extratos e cursores | Homologação de botão Ver extrato da conta no APK | PENDENTE_OPERACIONAL |
| M2116 | Livro-Razão, extratos e cursores | Retomada da sessão após perda de rede no aparelho | PENDENTE_OPERACIONAL |
| M2117 | Livro-Razão, extratos e cursores | Visualização de débitos e créditos reais reconciliados | PENDENTE_OPERACIONAL |
| M2118 | Livro-Razão, extratos e cursores | Consulta do extrato bancário pelo administrador | PENDENTE_OPERACIONAL |
| M2119 | Livro-Razão, extratos e cursores | Auditoria de leitura de extratos de membros | PENDENTE_OPERACIONAL |
| M2120 | Livro-Razão, extratos e cursores | Contas com milhões de lançamentos e snapshot estável | PENDENTE_OPERACIONAL |
| M2121 | Mercado Pago — habilitação operacional | OAuth Connect real por empresa | PENDENTE_OPERACIONAL |
| M2122 | Mercado Pago — habilitação operacional | Credenciais fora do aplicativo Android | PENDENTE_OPERACIONAL |
| M2123 | Mercado Pago — habilitação operacional | Validação de assinatura do webhook em produção | PENDENTE_OPERACIONAL |
| M2124 | Mercado Pago — habilitação operacional | Inbox persistente de webhook idempotente | PENDENTE_OPERACIONAL |
| M2125 | Mercado Pago — habilitação operacional | Consulta GET autenticada por collector | PENDENTE_OPERACIONAL |
| M2126 | Mercado Pago — habilitação operacional | Detecção real de reembolso parcial | PENDENTE_OPERACIONAL |
| M2127 | Mercado Pago — habilitação operacional | Detecção real de disputa e chargeback | PENDENTE_OPERACIONAL |
| M2128 | Mercado Pago — habilitação operacional | Tratamento de falha 429 com backoff | PENDENTE_OPERACIONAL |
| M2129 | Mercado Pago — habilitação operacional | Tratamento de indisponibilidade do PSP | PENDENTE_OPERACIONAL |
| M2130 | Mercado Pago — habilitação operacional | Expiração da tentativa de cobrança | PENDENTE_OPERACIONAL |
| M2131 | Mercado Pago — habilitação operacional | Validação do pagador com consentimento | PENDENTE_OPERACIONAL |
| M2132 | Mercado Pago — habilitação operacional | Valor real da taxa de PSP | PENDENTE_OPERACIONAL |
| M2133 | Mercado Pago — habilitação operacional | Confirmação financeira do settlement | PENDENTE_OPERACIONAL |
| M2134 | Mercado Pago — habilitação operacional | Extratos via canal autorizado pelo PSP | PENDENTE_OPERACIONAL |
| M2135 | Mercado Pago — habilitação operacional | Vínculo provedor-SaaS versus provedor-tenant | PENDENTE_OPERACIONAL |
| M2136 | Mercado Pago — habilitação operacional | Fila de execução com retry em OCI | PENDENTE_OPERACIONAL |
| M2137 | Mercado Pago — habilitação operacional | Diferenciação de testes e transações live_mode | PENDENTE_OPERACIONAL |
| M2138 | Mercado Pago — habilitação operacional | Rotação de segredos sem downtime | PENDENTE_OPERACIONAL |
| M2139 | Mercado Pago — habilitação operacional | Logs sem tokens ou dados sensíveis | PENDENTE_OPERACIONAL |
| M2140 | Mercado Pago — habilitação operacional | Go-live após homologação jurídica e técnica | PENDENTE_OPERACIONAL |
| M2141 | Capital, empréstimos e resultado | Baixa de contribuição somente após prova | PENDENTE_OPERACIONAL |
| M2142 | Capital, empréstimos e resultado | Não incluir aportes em receita de lucro | PENDENTE_OPERACIONAL |
| M2143 | Capital, empréstimos e resultado | Não reconhecer proposta como empréstimo desembolsado | PENDENTE_OPERACIONAL |
| M2144 | Capital, empréstimos e resultado | Repactuação de encargos segundo contrato | PENDENTE_OPERACIONAL |
| M2145 | Capital, empréstimos e resultado | Amortização na ordem de parcelas | PENDENTE_OPERACIONAL |
| M2146 | Capital, empréstimos e resultado | Multa única e mora simples válida | PENDENTE_OPERACIONAL |
| M2147 | Capital, empréstimos e resultado | Juros futuros excluídos na quitação | PENDENTE_OPERACIONAL |
| M2148 | Capital, empréstimos e resultado | Dívida contestada em revisão independente | PENDENTE_OPERACIONAL |
| M2149 | Capital, empréstimos e resultado | Capital-Dias com datas comprovadas | PENDENTE_OPERACIONAL |
| M2150 | Capital, empréstimos e resultado | Rateio pelos maiores restos | PENDENTE_OPERACIONAL |
| M2151 | Capital, empréstimos e resultado | Carteira técnica de resíduos segregada | PENDENTE_OPERACIONAL |
| M2152 | Capital, empréstimos e resultado | 15% remuneratórios administrativos sobre lucro elegível | PENDENTE_OPERACIONAL |
| M2153 | Capital, empréstimos e resultado | 85% de resultado conforme política aprovada | PENDENTE_OPERACIONAL |
| M2154 | Capital, empréstimos e resultado | Perdas e estornos no resultado com prova | PENDENTE_OPERACIONAL |
| M2155 | Capital, empréstimos e resultado | Relatório anual verificável por terceiro | PENDENTE_OPERACIONAL |
| M2156 | Capital, empréstimos e resultado | Revisão de contribuição duplicada | PENDENTE_OPERACIONAL |
| M2157 | Capital, empréstimos e resultado | Bloqueios de fechamento por disputa | PENDENTE_OPERACIONAL |
| M2158 | Capital, empréstimos e resultado | Verificação bancária de restituição de saída | PENDENTE_OPERACIONAL |
| M2159 | Capital, empréstimos e resultado | Autorização jurídica de compensação de dívida | PENDENTE_OPERACIONAL |
| M2160 | Capital, empréstimos e resultado | Pix real de distribuição somente após aprovação | PENDENTE_OPERACIONAL |
| M2161 | OCI, APK e infraestrutura | Provisionamento OCI isolado | PENDENTE_OPERACIONAL |
| M2162 | OCI, APK e infraestrutura | Ambiente staging em rede protegida | PENDENTE_OPERACIONAL |
| M2163 | OCI, APK e infraestrutura | TLS no endpoint de webhook | PENDENTE_OPERACIONAL |
| M2164 | OCI, APK e infraestrutura | Vault de tokens de cada tenant | PENDENTE_OPERACIONAL |
| M2165 | OCI, APK e infraestrutura | RLS com testes de carga no servidor | PENDENTE_OPERACIONAL |
| M2166 | OCI, APK e infraestrutura | Backup criptografado e restauração OCI | PENDENTE_OPERACIONAL |
| M2167 | OCI, APK e infraestrutura | Observabilidade sem vazamento de dados | PENDENTE_OPERACIONAL |
| M2168 | OCI, APK e infraestrutura | Circuit breaker do PSP | PENDENTE_OPERACIONAL |
| M2169 | OCI, APK e infraestrutura | Fila de jobs com limites por tenant | PENDENTE_OPERACIONAL |
| M2170 | OCI, APK e infraestrutura | Paginação em dataset grande | PENDENTE_OPERACIONAL |
| M2171 | OCI, APK e infraestrutura | APK assinado e instalado no aparelho | PENDENTE_OPERACIONAL |
| M2172 | OCI, APK e infraestrutura | Testes reais de UI por três perfis | PENDENTE_OPERACIONAL |
| M2173 | OCI, APK e infraestrutura | Compatibilidade com nova versão do Android | PENDENTE_OPERACIONAL |
| M2174 | OCI, APK e infraestrutura | Acessibilidade das mensagens contábeis | PENDENTE_OPERACIONAL |
| M2175 | OCI, APK e infraestrutura | Testes de suspensão e retomada da app | PENDENTE_OPERACIONAL |
| M2176 | OCI, APK e infraestrutura | Resiliência a perda de conexão no meio da consulta | PENDENTE_OPERACIONAL |
| M2177 | OCI, APK e infraestrutura | Migração real somente com autorização | PENDENTE_OPERACIONAL |
| M2178 | OCI, APK e infraestrutura | Plano de rollback de release | PENDENTE_OPERACIONAL |
| M2179 | OCI, APK e infraestrutura | Política LGPD sobre comprovantes | PENDENTE_OPERACIONAL |
| M2180 | OCI, APK e infraestrutura | Auditoria de segurança pré-produção | PENDENTE_OPERACIONAL |
| M2181 | CI, contratos e governança | Teste 400 valores em centavos | COBERTURA_SINTETICA_CI |
| M2182 | CI, contratos e governança | Teste 301 tarifas exatas | COBERTURA_SINTETICA_CI |
| M2183 | CI, contratos e governança | Teste 101 tarifas inválidas | COBERTURA_SINTETICA_CI |
| M2184 | CI, contratos e governança | Teste de divergência de liquidação | COBERTURA_SINTETICA_CI |
| M2185 | CI, contratos e governança | Teste de divergência contábil | COBERTURA_SINTETICA_CI |
| M2186 | CI, contratos e governança | Teste de status não aprovado | COBERTURA_SINTETICA_CI |
| M2187 | CI, contratos e governança | Teste de pagamento órfão em GET | COBERTURA_SINTETICA_CI |
| M2188 | CI, contratos e governança | Teste de demonstrativo órfão | COBERTURA_SINTETICA_CI |
| M2189 | CI, contratos e governança | Teste de lançamento órfão | COBERTURA_SINTETICA_CI |
| M2190 | CI, contratos e governança | Teste de caixa Master separado de tenant | COBERTURA_SINTETICA_CI |
| M2191 | CI, contratos e governança | Teste de caso sem evidências | COBERTURA_SINTETICA_CI |
| M2192 | CI, contratos e governança | Teste de navegação de 1000 páginas | COBERTURA_SINTETICA_CI |
| M2193 | CI, contratos e governança | Teste de cursor repetido | COBERTURA_SINTETICA_CI |
| M2194 | CI, contratos e governança | Teste de contrato FastAPI m2200 | COBERTURA_SINTETICA_CI |
| M2195 | CI, contratos e governança | Integração da suíte backend ao CI | COBERTURA_SINTETICA_CI |
| M2196 | CI, contratos e governança | Integração da suíte frontend ao CI | COBERTURA_SINTETICA_CI |
| M2197 | CI, contratos e governança | Preservação explícita dos bloqueios de dinheiro real | COBERTURA_SINTETICA_CI |
| M2198 | CI, contratos e governança | RLS e PostgreSQL 16/18 em CI descartável | COBERTURA_SINTETICA_CI |
| M2199 | CI, contratos e governança | PR #2 mantida em Draft sem merge | PENDENTE_OPERACIONAL |
| M2200 | CI, contratos e governança | Homologação técnica final do APK no aparelho | PENDENTE_OPERACIONAL |

**Inventário de escopo:** 160 tarefas; 73 com cobertura em lógica/testes sintéticos e 87 pendentes de integração operacional. A CI deve validar o commit final antes da homologação.

## Próximas liberações necessárias

1. Homologação de GET autenticado e histórico de liquidação com contas de teste Mercado Pago próprias por tenant; a confirmação oficial e a titularidade do recebedor não podem ser declaradas por fixtures.
2. Persistência transacional de webhook e resposta externa, deduplicação real, histórico de chargebacks e reversões, sem atingir banco local não migrado.
3. Política jurídica e de governança para reconhecer capital, dívida, juros, rateio e restituição com prova bancária.
4. Teste manual do botão `Ver extrato da conta` e dos botões `Anterior` e `Próxima` em APK atualizado, três perfis, extratos com 0/1/26+ lançamentos e sem saldo inventado.
5. Testes de deploy OCI, TLS, cofre de credenciais, segurança, backup/restore e homologação operacional.

## Checkpoint Termux (após PASS CI)

`git rev-parse --short HEAD`: comparar contra SHA final; `GET /api/health/features/m2200` confirmar `three_source_preflight_only=true`, `bank_reconciled=false`, `pix_enabled=false`, `real_payments_enabled=false`; PostgreSQL 5433 só `pg_isready`, sem migrations.

**Proibições:** nada de credenciais reais, money movement, merge da PR #2, force push, reaproveitar banco/repositório FRcaixinha 2.2.