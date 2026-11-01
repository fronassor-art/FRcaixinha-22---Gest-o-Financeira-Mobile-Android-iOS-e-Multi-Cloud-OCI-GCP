# Relatório técnico da rodada — FRcaixinha 2.2

Data: 01/11/2026 UTC. Repositório: fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP. Branch de trabalho: atualizacao-ai-studio-9b46a63187. PR [#2](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/pull/2), aberta como rascunho contra main. Base remota auditada nesta rodada: 9200d4a831739c4a5131049f3fc7fd88a73d49d7; main inicial: ad61a1e33485f91d4425455c31561c860465b2ec. O HEAD final é o commit da PR que contém este relatório. Nenhum merge na main.

## Resumo executivo

A rodada melhorou sessões PostgreSQL de homologação, seleção de vínculos, isolamento de leitura/RLS com dados sintéticos, integridade do ledger no banco, cálculo Price com primeiro período irregular, resposta individual dos endpoints de escrita de empréstimo, backup age/restauração descartável e identificação dos demonstradores de bolão e rifa. A autorização anual de autoempréstimo tem motor puro testado e o pedido não pode ocultar a identidade do administrador via vínculo de membro, mas assinaturas persistentes e revalidação transacional ainda não existem; voto antigo e aprovação permanecem bloqueados. Pix, desembolso, quitação e fechamento continuam indisponíveis para dinheiro real. O APK debug de CI é artefato de teste, sem prova visual no aparelho.

O [checkpoint completo](CHECKPOINT_CONTRATO_2026-11-01.md) lista as 147 cláusulas, requisito, arquivo/função, teste ou ausência de teste, estado e pendência. Contagem: CONCLUÍDO E TESTADO 0; PARCIAL 58; BLOQUEADO 50; AUSENTE 0; DIVERGENTE 5; NÃO VERIFICADO 34. A classificação conservadora não equipara compilação a conformidade. [Fotografia anterior](CHECKPOINT_CONTRATO_HISTORICO_74b9a543.md) preservada; 86 rótulos mudaram.

## Fontes documentais e escolhas expressas

Foram extraídos integralmente os dois PDFs do próprio repositório: Contrato Técnico Mestre — Cláusulas Originais (38 páginas; SHA-256 7b28d5d5cf773fb5c35194bce64ebfdfec4d67422bafac4595a6662b4f45f468) e Caderno Mestre — Regras e Cláusulas, Texto Original (57 páginas; SHA-256 94d2a15c54d3f5982c09fe78762ae0f1c76e03fa644cb05a6404f5c7b2feb0f6). Ambos identificam 147 cláusulas na mesma ordem; diferenças de apresentação/texto não autorizam escolher silenciosamente uma redação. As cópias em dist são byte-idênticas; não foi identificada versão documental mais nova. O checkpoint antigo não reflete as proteções posteriores contra convite com falso sucesso e autoaprovação.

A cláusula 1.8 cita Flutter, mas a instrução expressa do proprietário exige manter React + Capacitor. As cláusulas 1.6 e 14 restringem a operação de rifa; a instrução expressa preserva rifa e bolão como demonstradores, sem cobrar, vender, sortear ou lançar dinheiro real. Para 2027, apuração de Capital-Dias vai de 01/01/2027 a 31/12/2027; a liquidação prevista em 10/01/2028 não amplia o período.

## Escopo e evidência por frente

| Frente | Implementado nesta rodada | Evidência e estado restante |
|---|---|---|
| Login/sessões | Sessões com hash de token no PostgreSQL, expiração, revogação/logout; contextos por vínculo. backend/app/routers/auth.py:39,88,116,145; dependencies.py; migrations/008. | CI PostgreSQL sintético testou login, revogação, expiração, vínculos e negação de acesso. O login segue limitado a FRCAIXINHA_TEST_AUTH e não está pronto para produção; provisionamento real, TLS e proteção operacional pendentes. |
| Frontend | Seletor de vínculo, reinicialização profunda dos dados demonstrativos em login/logout/troca, 401 invalida sessão; aviso geral de homologação. src/App.tsx:56,152,265,282; services/authService.ts; financialApiService.ts; store.ts: loadState, setAuthenticatedContext, clearAuthenticatedContext. | Contribuições consultam API; muitos painéis ainda usam seed/local state. server_integration.test.ts cobre descarte de mutações fictícias entre contas; sem teste visual no aparelho ou cobertura completa dos componentes. |
| PostgreSQL/RLS | Migrações 008–010; papel auth separado; políticas de leitura por tenant/contexto e FKs compostas em entidades selecionadas. migrations/009. | CI PostgreSQL 16 com papéis NOSUPERUSER/NOBYPASSRLS, dois tenants e usuários sintéticos. CRUD integral de todas as tabelas e ataques de concorrência ainda não comprovados. Nenhuma migration foi aplicada ao banco real do Termux. |
| Contribuições | Leitura existente via API e RLS ampliada. | Cobrança, confirmação, contabilização e estorno reais bloqueados. |
| Empréstimos | Price Decimal com taxa irregular por dias/30, soma de fatores de desconto, vencimento dia 10 do mês seguinte, ajuste final; pedido respeita prazo máximo da política do tenant e resposta individual; loans.py:29–109,249. | test_price_contract.py cobre casos matemáticos, resposta individual e recusa de prazo acima da política sem escrita, sem provar uma transação API/PG completa. Política por tenant, mora/pagamento parcial integrados, confirmação de desembolso e quitação continuam parciais/bloqueados. |
| Autorização anual | annual_consent.py:37 calcula unanimidade dos demais membros ativos e falha com zero outros ou admin sem vínculo; consents.py:14,27 bloqueia voto legado. | test_annual_consent.py cobre ingresso, revogação, versão, ciclo e casos negativos; test_price_contract.py cobre o administrador que pede como membro e a recusa da aprovação de registro antigo mal marcado. Falta persistência de assinaturas e revalidação em aprovação/reserva/envio. |
| Ledger | migrations/010 impõe FK do tenant, referência única e DR=CR por gatilho diferido; UPDATE/DELETE retirados do papel da aplicação. | CI testa postagem sintética, duplicata, rollback e FK cruzada. Falta serviço autoritativo de postagem, idempotência por operação, concorrência e reconciliação. |
| Fechamento | Corte 31/12 expresso; cálculo local parcial. | Fechamento por estados, Capital-Dias a partir de eventos persistidos, maiores restos e liquidação confirmada ausentes/bloqueados. Capital de membros não foi alterado nesta rodada. |
| Mercado Pago/Pix | Adaptador e testes simulados existentes, documentação oficial conferida; [plano de homologação](MERCADO_PAGO_HOMOLOGACAO.md). | Sem OAuth, credenciais, conta homologada, webhook persistente, consulta autenticada, conciliação ou Pix real. Endpoints de pagamento/desembolso/baixa permanecem bloqueados. |
| Bolão/rifa | Arquivos, dados e funções preservados; filtro visual pelo tenant atual e avisos explícitos de demonstração dentro dos dois módulos. src/components/BolaoModuleView.tsx; RaffleModuleView.tsx; PixModal.tsx. | O estado é local e não oferece isolamento servidor; textos/processos restantes precisam revisão funcional e jurídica antes de qualquer operação. Nenhum resultado oficial foi validado. |
| Backup/Termux | scripts/backup_age.sh, restore_disposable_ci.sh; [instruções](BACKUP_TERMUX.md). | CI cifra e restaura banco descartável com registro sintético. Execução no Termux e reconciliação de backup anterior a pagamento pendentes. |
| Android | React + Capacitor preservados; [plano de assinatura durável](ASSINATURA_ANDROID.md). | CI compila APK debug e publica artefato por 7 dias. Não foi instalado/testado nesta rodada. Keystore release fora do repositório; assinatura durável não configurada. |

### Exemplo Price de R$ 500,00

Para taxa mensal de 20% e cinco parcelas regulares, a prestação teórica é P × i / (1 − (1+i)^−n). O motor usa Decimal e arredonda a prestação uniforme a R$ 167,19; ajusta a quinta a R$ 167,20, resultando R$ 335,96 de juros e R$ 835,96 a pagar. A soma de amortizações é R$ 500,00 e o saldo final zero, conforme test_price_contract.py. Quando o primeiro período é irregular, usa i1 = 0,20 × dias/30 e prestação P / soma dos fatores de desconto; as datas devem caber no ciclo. Esse teste matemático não prova juros de um empréstimo desembolsado. Rótulos financeiros das telas seed e política configurável ainda podem divergir do backend; requer confronto visual e de API. A expressão “Taxa ZERO” observada em versão anterior do celular não foi revalidada neste novo APK.

## Achados priorizados

1. CRÍTICO — Dinheiro real não pode ser habilitado: falta OAuth/credenciais segregadas, webhook assinado persistente, consulta autenticada, idempotência econômica e conciliação antes da baixa (cláusulas 9.1–9.9). backend/app/routers/pix.py e loans.py:410,483,620 retornam bloqueio. Nenhuma credencial foi solicitada ou utilizada.
2. ALTO — Consentimento anual não está persistido nem integrado transacionalmente. Um voto por operação não cumpre a cláusula 2.5. backend/app/annual_consent.py:37 é lógica pura; routers/consents.py:27 e loans.py:321 bloqueiam avanço. Não marcar autoempréstimo pronto.
3. ALTO — Ledger tem invariantes no banco, mas falta postagem autoritativa, concorrência e vínculo ao provedor; migrations/010 não prova liquidação financeira.
4. ALTO — Produção não usa login desta rodada: FRCAIXINHA_TEST_AUTH e AUTH_DATABASE_URL são gates de homologação. Sessão/RLS testadas no CI não substituem configuração segura, provisionamento e operação.
5. MÉDIO — Painéis e demonstradores usam estado local/seed. Filtro visual por caixinha em RaffleModuleView.tsx e BolaoModuleView.tsx protege a apresentação, não equivale a autorização no servidor.
6. MÉDIO — Regra financeira por tenant e fechamento anual completo não foram provados; loans.py ainda tem valores iniciais fixos e rotas bloqueadas. Cláusulas 4.1, 8 e 10.
7. MÉDIO — Backup age/restauração funcionou em CI, mas faltam ensaio no Termux e plano transacional de reconciliação pós-restauração. Um backup anterior a pagamento não autoriza segunda cobrança.
8. MÉDIO — Textos antigos de “oficial/homologado” e botões Pix em demonstradores podiam sugerir serviço real; os rótulos mais visíveis foram corrigidos e o PixModal não baixa saldo, mas revisão visual completa ainda pendente.

## Verificações e ambientes

GitHub Actions usa Node 22, npm ci do package-lock, npm run lint, npm run test:audit, teste TypeScript de integração e npm run build; Python 3.11 com requirements, FastAPI, pytest; PostgreSQL 16 descartável e papéis sem SUPERUSER/BYPASSRLS; Java 21, npm run cap:build e ./gradlew --no-daemon assembleDebug. Sem --force ou --legacy-peer-deps. O CI não usa banco do celular, credenciais Mercado Pago nem serviços pagos.

| Execução | Resultado observado |
|---|---|
| [41343697413](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41343697413) | PASS, quatro jobs: web, API, PostgreSQL e APK debug após sessões/contextos. |
| [41344857688](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41344857688) | PASS, quatro jobs; RLS/integridade e backup/restauração descartável. |
| [41345573838](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41345573838) | PASS, quatro jobs; Price e scripts/documentação. |
| [41345757397](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41345757397) | PASS, quatro jobs; invariantes do ledger. |
| [41346644392](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41346644392) | PASS, quatro jobs; consentimento anual e checklist. |
| [41346866474](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41346866474) | PASS, quatro jobs; telas de rifa/bolão, web, API, PostgreSQL e APK debug. [Artefato APK de teste](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41346866474/artifacts/13099044948), ZIP de 5.081.951 bytes, retenção de 7 dias. |

Os comandos de CI acima saíram com código 0 nos respectivos steps; os tempos e logs por step estão nas execuções. No Termux desta sessão, PYTHONPATH=backend backend/.venv/bin/python -m pytest ... falhou com código 127 porque a venv não existe; PYTHONPATH=backend python3 -m pytest ... falhou com código 4 porque pytest-asyncio não está instalado. Isso não foi mascarado: o mesmo conjunto foi executado no GitHub Actions com dependências limpas. npm run lint local também não é prova nesta arquitetura Termux devido ao pacote nativo @typescript/typescript-android-arm64 ausente; a execução Linux no CI passou. Build web e APK são jobs distintos. O artefato de teste se chama frcaixinha-ai-studio-debug, retido sete dias na execução correspondente.

### Comandos e tempos do CI de 41346644392

Tempos arredondados ao segundo, extraídos dos steps do GitHub Actions. Código de saída 0 corresponde ao step PASS; o link da execução contém os logs detalhados. Os jobs rodaram em paralelo.

| Comando ou step | Ambiente | Duração | Saída | Estado |
|---|---|---:|---:|---|
| npm ci (frontend) | Ubuntu, Node 22 | 7 s | 0 | PASS |
| npm run lint | Ubuntu, Node 22 | menor que 1 s | 0 | PASS |
| npm run test:audit | Ubuntu, Node 22 | 1 s | 0 | PASS |
| npx tsx src/tests/server_integration.test.ts | Ubuntu, Node 22 | menor que 1 s | 0 | PASS |
| npm run build | Ubuntu, Node 22 | 1 s | 0 | PASS web |
| python -m pip install -r backend/requirements.txt | Ubuntu, Python 3.11 | 4 s no job API; 16 s no job PostgreSQL | 0 | PASS |
| python -m pytest ... (API sem banco) | Ubuntu, Python 3.11 | 1 s | 0 | PASS |
| psql -f backend/migrations/001...010 | Ubuntu, PostgreSQL 16 descartável | 1 s | 0 | PASS |
| python -m pytest ... (RLS, isolamento, bootstrap) | PostgreSQL 16, papéis de app/auth sem SUPERUSER nem BYPASSRLS | 7 s somados | 0 | PASS |
| bash backend/scripts/backup_age.sh e restore_disposable_ci.sh | PostgreSQL 16 descartável, age | 8 s (step incluiu instalação age) | 0 | PASS |
| npm ci; npm run cap:build | Ubuntu, Node 22/Capacitor 8 | 5 s; 2 s | 0 | PASS web+sync |
| ./gradlew --no-daemon assembleDebug | Ubuntu, Java 21 | 100 s | 0 | PASS APK debug |

### Arquivos alterados frente à base 9200d4a

Modificados: .github/workflows/validacao-atualizacao.yml, .gitignore, backend/app/dependencies.py, backend/app/routers/auth.py, backend/app/routers/consents.py, backend/app/routers/loans.py, backend/tests/test_rls_isolation_ci.py, backend/tests/test_security_guards.py, src/App.tsx, src/components/BolaoModuleView.tsx, src/components/PixModal.tsx, src/components/RaffleModuleView.tsx, src/services/authService.ts, src/services/financialApiService.ts, src/services/store.ts, src/tests/server_integration.test.ts e docs/CHECKPOINT_CONTRATO_2026-11-01.md.

Adicionados: backend/app/annual_consent.py, backend/migrations/008_persistent_auth_sessions.sql, 009_tenant_context_and_references.sql, 010_ledger_integrity.sql, backend/scripts/backup_age.sh, restore_disposable_ci.sh, backend/tests/test_annual_consent.py, test_price_contract.py, docs/ASSINATURA_ANDROID.md, BACKUP_TERMUX.md, CHECKPOINT_CONTRATO_HISTORICO_74b9a543.md, MERCADO_PAGO_HOMOLOGACAO.md e este relatório. Nenhum arquivo foi excluído. O APK gerado, dist, node_modules, caches, chave age, keystore e segredos não foram adicionados ao commit.

## Pendências e próxima sequência

1. Implementar assinatura anual versionada no PostgreSQL, revalidação na aprovação/reserva/envio e testes de concorrência/ingresso/revogação.
2. Ligar ledger autoritativo às obrigações, com comandos idempotentes e rollback sob concorrência; só depois implementar fechamento 2027 com eventos, maiores restos e preservação de capital.
3. Expandir API e telas por domínio, com vazio/carregamento/erro/401, isolamento de estado e testes de componentes; revisar toda comunicação de rifa e bolão como demonstração.
4. Preparar OAuth e conta por tenant, cofre de credenciais, eventos persistentes e consulta autenticada Mercado Pago; executar homologação apenas quando conta, capacidade e endpoint público estiverem disponíveis. Pix de saída exige prova específica do provedor.
5. Ensaiar backup/restauração no Termux em banco descartável próprio e reconciliação após restauração; provisionar contas e configurar TLS sem versionar segredos.
6. Definir assinatura release durável fora do repositório e testar APK debug no aparelho: login/logout/troca de contexto, dados entre duas caixinhas, responsividade de parcelas e barra inferior, valor e rótulos Price, demonstradores, rede/erro/expiração. Não executar transações reais.
7. Executar AT-01–AT-50 de forma rastreável. A PR permanece rascunho até critérios documentais, técnicos e externos satisfeitos; não mesclar agora.

Bloqueios externos: credenciais e conta homologada do Mercado Pago, autorização OAuth/capacidade de Pix de saída, endpoint HTTPS público, aprovação jurídica/regulatória para operação, Termux e aparelho para ensaios locais. Esses bloqueios não impedem desenvolvimento e testes sintéticos adicionais.

Não foram feitas operações financeiras reais, deployment, uso de segredos, migrations no banco real, correções de regra financeira fora dos pontos descritos ou merge na main. Bolão e rifa foram preservados por determinação expressa do proprietário, apenas como demonstradores. O APK debug não está pronto para uso financeiro real.
