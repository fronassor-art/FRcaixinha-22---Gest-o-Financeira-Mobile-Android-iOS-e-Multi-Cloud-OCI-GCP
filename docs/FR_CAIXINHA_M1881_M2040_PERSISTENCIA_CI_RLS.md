# FR Caixinha AI Studio — M1881–M2040 (160 controles de continuidade)

**Base homologada:** `5c09aee32899452d49e716c38c29ae26556869bc` (M1880, CI 6/6 PASS). Branch `atualizacao-ai-studio-9b46a63187`, PR #2 **Draft**, projeto **AI Studio** distinto do FRcaixinha 2.2 independente.

## Implementação deste pacote

- Migração de laboratório `backend/ci_migrations/031_mp_sandbox_evidence_ci_only.sql`. Ela NÃO está na pasta `backend/migrations` usada pelo Termux e contém barreiras no banco (`current_database()='frcaixinha_ci'`) e sinalização explícita de CI para **impedir aplicação local**.
- Tabela de eventos sintéticos com RLS forçado, FK composta (tenant, membership), unicidade de idempotência, eventos e aprovações; campos `bank_reconciled=false`, `financial_effect_applied=false`, `settlement_authorized=false` imutáveis por CHECK. Aplicação pode somente SELECT.
- Função `append_mp_sandbox_evidence_ci`: administrador ativo do próprio tenant, advisory lock por operação de provedor, replay idempotente, rejeição de reaproveitamento conflitante, créditos sintéticos duplicados, reembolsos sem aprovação e reversões acima do valor; **não é integração Mercado Pago real**.
- Roteador de leituras `backend/app/routers/sandbox_evidence_ci.py`: prévia por membro e administrador, paginação keyset, nunca escreve. É **registrado somente** com `FRCAIXINHA_CI_ISOLATED=1` + `AI_STUDIO_M2040_CI_EVIDENCE_READS=1` fora de produção; banco exige ainda `frcaixinha_ci`.
- Diagnóstico `GET /api/health/features/m2040` expõe somente invariantes, bloqueios reais e estado de registro de rotas de CI.
- Novos testes de contrato e PostgreSQL CI 16/18 para idempotência, RLS, estornos, disputa, isolamento Master, extrato por membro, paginação e bloqueios de liquidação; continuam também todos os testes existentes da CI.

### Regra de nomenclatura e alcance

`CI_SINTETICO` significa que existe código ou teste de laboratório, **sem prova bancária e sem autorização de operações reais**. `PENDENTE_OPERACIONAL` significa integração ou homologação não entregue. Nenhum controle recebe marcação PASS até a CI executar no SHA exato; mais importante, uma CI PASS não significa que a integração operacional foi concluída.

## Matriz de 160 tarefas

| ID | Frente | Controle | Estado |
|---|---|---|---|
| M1881 | Migração CI e modelo durável | Isolar migração 031 fora do migrador local | CI_SINTETICO |
| M1882 | Migração CI e modelo durável | Exigir base frcaixinha_ci descartável | CI_SINTETICO |
| M1883 | Migração CI e modelo durável | Exigir flag GUC CI por sessão | CI_SINTETICO |
| M1884 | Migração CI e modelo durável | Tabela de evidências sintéticas append-only | CI_SINTETICO |
| M1885 | Migração CI e modelo durável | UUID por evento | CI_SINTETICO |
| M1886 | Migração CI e modelo durável | Sequência imutável por evento | CI_SINTETICO |
| M1887 | Migração CI e modelo durável | Vínculo obrigatório tenant/membro | CI_SINTETICO |
| M1888 | Migração CI e modelo durável | Ator auditável com FK | CI_SINTETICO |
| M1889 | Migração CI e modelo durável | Tipos de eventos em allowlist | CI_SINTETICO |
| M1890 | Migração CI e modelo durável | Valores em centavos inteiros | CI_SINTETICO |
| M1891 | Migração CI e modelo durável | Valor zero somente em disputa | CI_SINTETICO |
| M1892 | Migração CI e modelo durável | Marcar source como fixture sem prova | CI_SINTETICO |
| M1893 | Migração CI e modelo durável | bank_reconciled sempre false | CI_SINTETICO |
| M1894 | Migração CI e modelo durável | financial_effect_applied sempre false | CI_SINTETICO |
| M1895 | Migração CI e modelo durável | settlement_authorized sempre false | CI_SINTETICO |
| M1896 | Migração CI e modelo durável | Plano de migração homologada para staging OCI | PENDENTE_OPERACIONAL |
| M1897 | Migração CI e modelo durável | Backfill de eventos reais autorizados | PENDENTE_OPERACIONAL |
| M1898 | Migração CI e modelo durável | Rotação de chaves de idempotência persistentes | PENDENTE_OPERACIONAL |
| M1899 | Migração CI e modelo durável | Retenção de documentos segundo LGPD | PENDENTE_OPERACIONAL |
| M1900 | Migração CI e modelo durável | Assinatura externa de documentos de prova | PENDENTE_OPERACIONAL |
| M1901 | Idempotência e conflitos SQL | Função SECURITY DEFINER controlada | CI_SINTETICO |
| M1902 | Idempotência e conflitos SQL | Advisory lock por provider_payment_id | CI_SINTETICO |
| M1903 | Idempotência e conflitos SQL | Chave idempotente por tenant | CI_SINTETICO |
| M1904 | Idempotência e conflitos SQL | Mesmo payload retorna mesmo UUID | CI_SINTETICO |
| M1905 | Idempotência e conflitos SQL | Chave reutilizada com outro valor recusada | CI_SINTETICO |
| M1906 | Idempotência e conflitos SQL | Uma aprovação por payment_id global | CI_SINTETICO |
| M1907 | Idempotência e conflitos SQL | Reembolso só após aprovação sintética | CI_SINTETICO |
| M1908 | Idempotência e conflitos SQL | Chargeback só após aprovação sintética | CI_SINTETICO |
| M1909 | Idempotência e conflitos SQL | Disputa só após aprovação sintética | CI_SINTETICO |
| M1910 | Idempotência e conflitos SQL | Reversão limitada ao crédito original | CI_SINTETICO |
| M1911 | Idempotência e conflitos SQL | Estorno parcial conserva centavos | CI_SINTETICO |
| M1912 | Idempotência e conflitos SQL | Eventos duplicados de disputa rejeitados | CI_SINTETICO |
| M1913 | Idempotência e conflitos SQL | Chargeback repetido rejeitado | CI_SINTETICO |
| M1914 | Idempotência e conflitos SQL | Reenvio concorrente em múltiplas instâncias | PENDENTE_OPERACIONAL |
| M1915 | Idempotência e conflitos SQL | Teste de deadlock e retry SQL | PENDENTE_OPERACIONAL |
| M1916 | Idempotência e conflitos SQL | Inbox HTTP real idempotente | PENDENTE_OPERACIONAL |
| M1917 | Idempotência e conflitos SQL | Persistência do comprovante do PSP com hash assinado | PENDENTE_OPERACIONAL |
| M1918 | Idempotência e conflitos SQL | Validação cross-request do payer | PENDENTE_OPERACIONAL |
| M1919 | Idempotência e conflitos SQL | Reconciliação pós-chargeback durável | PENDENTE_OPERACIONAL |
| M1920 | Idempotência e conflitos SQL | Aplicar efeito contábil exclusivamente após evidência real | PENDENTE_OPERACIONAL |
| M1921 | RBAC, RLS e privilégio mínimo | RLS ENABLE no diário | CI_SINTETICO |
| M1922 | RBAC, RLS e privilégio mínimo | RLS FORCE para o proprietário | CI_SINTETICO |
| M1923 | RBAC, RLS e privilégio mínimo | App sem INSERT direto | CI_SINTETICO |
| M1924 | RBAC, RLS e privilégio mínimo | App sem UPDATE direto | CI_SINTETICO |
| M1925 | RBAC, RLS e privilégio mínimo | App sem DELETE direto | CI_SINTETICO |
| M1926 | RBAC, RLS e privilégio mínimo | Auth sem SELECT do diário | CI_SINTETICO |
| M1927 | RBAC, RLS e privilégio mínimo | Verifier sem SELECT do diário | CI_SINTETICO |
| M1928 | RBAC, RLS e privilégio mínimo | Master sem papel de leitura tenant | CI_SINTETICO |
| M1929 | RBAC, RLS e privilégio mínimo | Admin vê somente seu tenant | CI_SINTETICO |
| M1930 | RBAC, RLS e privilégio mínimo | Membro vê somente próprio vínculo | CI_SINTETICO |
| M1931 | RBAC, RLS e privilégio mínimo | Membro não executa inserção sintética | CI_SINTETICO |
| M1932 | RBAC, RLS e privilégio mínimo | Função exige admin ativo | CI_SINTETICO |
| M1933 | RBAC, RLS e privilégio mínimo | Função confirma membro pertencente ao tenant | CI_SINTETICO |
| M1934 | RBAC, RLS e privilégio mínimo | Função confirma tenant da sessão | CI_SINTETICO |
| M1935 | RBAC, RLS e privilégio mínimo | Conta recebedora da plataforma fora do diário tenant | PENDENTE_OPERACIONAL |
| M1936 | RBAC, RLS e privilégio mínimo | RLS em integração OCI de produção | PENDENTE_OPERACIONAL |
| M1937 | RBAC, RLS e privilégio mínimo | Permissões anônimas negativas no novo schema | PENDENTE_OPERACIONAL |
| M1938 | RBAC, RLS e privilégio mínimo | Rate limiting da leitura do histórico | PENDENTE_OPERACIONAL |
| M1939 | RBAC, RLS e privilégio mínimo | Auditoria de troca de tenant nas sessões | PENDENTE_OPERACIONAL |
| M1940 | RBAC, RLS e privilégio mínimo | Testes com concorrência extrema entre papéis | PENDENTE_OPERACIONAL |
| M1941 | Leitura por membro e paginação | Rota de leitura própria em sandbox | CI_SINTETICO |
| M1942 | Leitura por membro e paginação | Rota admin por vínculo do tenant | CI_SINTETICO |
| M1943 | Leitura por membro e paginação | GET read-only sem SQL UPDATE | CI_SINTETICO |
| M1944 | Leitura por membro e paginação | Página com teto de 100 eventos | CI_SINTETICO |
| M1945 | Leitura por membro e paginação | Keyset event_seq estável | CI_SINTETICO |
| M1946 | Leitura por membro e paginação | has_more não truncado silenciosamente | CI_SINTETICO |
| M1947 | Leitura por membro e paginação | Data e referência de evento na resposta | CI_SINTETICO |
| M1948 | Leitura por membro e paginação | Natureza sintética explícita | CI_SINTETICO |
| M1949 | Leitura por membro e paginação | Bloqueios financeiros explícitos | CI_SINTETICO |
| M1950 | Leitura por membro e paginação | Router CI opt-in por ambiente | CI_SINTETICO |
| M1951 | Leitura por membro e paginação | Router desabilitado no Termux por padrão | CI_SINTETICO |
| M1952 | Leitura por membro e paginação | Extrato do provedor autenticado por tenant | PENDENTE_OPERACIONAL |
| M1953 | Leitura por membro e paginação | Extrato do associado reconciliado | PENDENTE_OPERACIONAL |
| M1954 | Leitura por membro e paginação | Painel de auditoria do administrador | PENDENTE_OPERACIONAL |
| M1955 | Leitura por membro e paginação | Redação LGPD de dados de terceiros | PENDENTE_OPERACIONAL |
| M1956 | Leitura por membro e paginação | Recuperação segura de cursor entre sessões | PENDENTE_OPERACIONAL |
| M1957 | Leitura por membro e paginação | Teste de corrida com eventos novos durante paginação | PENDENTE_OPERACIONAL |
| M1958 | Leitura por membro e paginação | CSP para exibição de comprovantes | PENDENTE_OPERACIONAL |
| M1959 | Leitura por membro e paginação | Download individual com histórico completo | PENDENTE_OPERACIONAL |
| M1960 | Leitura por membro e paginação | Validação no APK físico dos botões Anterior/Próxima | PENDENTE_OPERACIONAL |
| M1961 | Mercado Pago multiempresa | OAuth Connect por empresa e isolamento de token | PENDENTE_OPERACIONAL |
| M1962 | Mercado Pago multiempresa | Credencial da plataforma Master segregada | PENDENTE_OPERACIONAL |
| M1963 | Mercado Pago multiempresa | Autorização por webhook HMAC com janela | PENDENTE_OPERACIONAL |
| M1964 | Mercado Pago multiempresa | Obtenção GET authoritative do provider | PENDENTE_OPERACIONAL |
| M1965 | Mercado Pago multiempresa | Comparação de collector_id por tenant | PENDENTE_OPERACIONAL |
| M1966 | Mercado Pago multiempresa | Valores em centavos sem float | PENDENTE_OPERACIONAL |
| M1967 | Mercado Pago multiempresa | Moeda BRL obrigatória | PENDENTE_OPERACIONAL |
| M1968 | Mercado Pago multiempresa | Identificador provider persistido | PENDENTE_OPERACIONAL |
| M1969 | Mercado Pago multiempresa | Idempotência em POST Pix real | PENDENTE_OPERACIONAL |
| M1970 | Mercado Pago multiempresa | Replay HTTP durável e auditável | PENDENTE_OPERACIONAL |
| M1971 | Mercado Pago multiempresa | Expiração da intenção Pix | PENDENTE_OPERACIONAL |
| M1972 | Mercado Pago multiempresa | Chargeback do PSP reconciliado | PENDENTE_OPERACIONAL |
| M1973 | Mercado Pago multiempresa | Refund integral e parcial do PSP | PENDENTE_OPERACIONAL |
| M1974 | Mercado Pago multiempresa | Fila com backoff e dead-letter | PENDENTE_OPERACIONAL |
| M1975 | Mercado Pago multiempresa | Webhook duplicado entre instâncias | PENDENTE_OPERACIONAL |
| M1976 | Mercado Pago multiempresa | Pagador compatível com obrigação | PENDENTE_OPERACIONAL |
| M1977 | Mercado Pago multiempresa | Tratamento de falha de rede | PENDENTE_OPERACIONAL |
| M1978 | Mercado Pago multiempresa | Sanitização dos segredos em logs | PENDENTE_OPERACIONAL |
| M1979 | Mercado Pago multiempresa | Homologação em contas de teste oficiais | PENDENTE_OPERACIONAL |
| M1980 | Mercado Pago multiempresa | Autorização de go-live por operação financeira | PENDENTE_OPERACIONAL |
| M1981 | Ledger, capital e fechamento anual | Vincular cada cota a comprovante externo | PENDENTE_OPERACIONAL |
| M1982 | Ledger, capital e fechamento anual | Confirmar principal por liquidação efetiva | PENDENTE_OPERACIONAL |
| M1983 | Ledger, capital e fechamento anual | Saldos de capital por membro reconciliados | PENDENTE_OPERACIONAL |
| M1984 | Ledger, capital e fechamento anual | Impedir proposta empréstimo virar dívida | PENDENTE_OPERACIONAL |
| M1985 | Ledger, capital e fechamento anual | Amortização parcela mais antiga | PENDENTE_OPERACIONAL |
| M1986 | Ledger, capital e fechamento anual | Separar juros futuros de dívida atual | PENDENTE_OPERACIONAL |
| M1987 | Ledger, capital e fechamento anual | Mora simples conforme contrato aceito | PENDENTE_OPERACIONAL |
| M1988 | Ledger, capital e fechamento anual | Multa única por obrigação admissível | PENDENTE_OPERACIONAL |
| M1989 | Ledger, capital e fechamento anual | Prevenir anatocismo e reprocessamento | PENDENTE_OPERACIONAL |
| M1990 | Ledger, capital e fechamento anual | Reversão contábil por chargeback | PENDENTE_OPERACIONAL |
| M1991 | Ledger, capital e fechamento anual | Fechamento anual de receitas realizadas | PENDENTE_OPERACIONAL |
| M1992 | Ledger, capital e fechamento anual | Despesas e perdas documentalmente aprovadas | PENDENTE_OPERACIONAL |
| M1993 | Ledger, capital e fechamento anual | Remuneração administrativa 15% sobre lucro válido | PENDENTE_OPERACIONAL |
| M1994 | Ledger, capital e fechamento anual | Pool membros 85% quando aplicável | PENDENTE_OPERACIONAL |
| M1995 | Ledger, capital e fechamento anual | Capital-Dias baseado em instantes reconciliados | PENDENTE_OPERACIONAL |
| M1996 | Ledger, capital e fechamento anual | Maiores restos com desempate auditável | PENDENTE_OPERACIONAL |
| M1997 | Ledger, capital e fechamento anual | Carteira técnica de resíduos | PENDENTE_OPERACIONAL |
| M1998 | Ledger, capital e fechamento anual | Disputa aberta bloqueia distribuição | PENDENTE_OPERACIONAL |
| M1999 | Ledger, capital e fechamento anual | Restituição de saída exige prova e autoridade | PENDENTE_OPERACIONAL |
| M2000 | Ledger, capital e fechamento anual | Nenhum Pix automático sem autorização | PENDENTE_OPERACIONAL |
| M2001 | Android, OCI e experiência | Painel sintético separado do saldo real | PENDENTE_OPERACIONAL |
| M2002 | Android, OCI e experiência | Indicador visual de valor não conciliado | PENDENTE_OPERACIONAL |
| M2003 | Android, OCI e experiência | Indicador de revisão e contestação | PENDENTE_OPERACIONAL |
| M2004 | Android, OCI e experiência | Avisos sobre chargeback | PENDENTE_OPERACIONAL |
| M2005 | Android, OCI e experiência | Filtro por período no histórico | PENDENTE_OPERACIONAL |
| M2006 | Android, OCI e experiência | Extrato individual completo | PENDENTE_OPERACIONAL |
| M2007 | Android, OCI e experiência | Extrato admin com seleção de membro | PENDENTE_OPERACIONAL |
| M2008 | Android, OCI e experiência | Acessibilidade em tabelas financeiras | PENDENTE_OPERACIONAL |
| M2009 | Android, OCI e experiência | Paginação Anterior/Próxima no aparelho | PENDENTE_OPERACIONAL |
| M2010 | Android, OCI e experiência | Teste de perda de rede e reconexão | PENDENTE_OPERACIONAL |
| M2011 | Android, OCI e experiência | Teste de expiração de sessão no aparelho | PENDENTE_OPERACIONAL |
| M2012 | Android, OCI e experiência | Teste update APK com assinatura | PENDENTE_OPERACIONAL |
| M2013 | Android, OCI e experiência | Deploy staging OCI sem contato com o banco local | PENDENTE_OPERACIONAL |
| M2014 | Android, OCI e experiência | Banco OCI isolado e política de backup | PENDENTE_OPERACIONAL |
| M2015 | Android, OCI e experiência | Vault para segredos e OAuth | PENDENTE_OPERACIONAL |
| M2016 | Android, OCI e experiência | TLS HTTPS e pinning quando adequado | PENDENTE_OPERACIONAL |
| M2017 | Android, OCI e experiência | RLS CI replicado em OCI staging | PENDENTE_OPERACIONAL |
| M2018 | Android, OCI e experiência | Restore em servidor descartável | PENDENTE_OPERACIONAL |
| M2019 | Android, OCI e experiência | Teste de carga de contas/associações | PENDENTE_OPERACIONAL |
| M2020 | Android, OCI e experiência | Revisão de segurança antes de publicação | PENDENTE_OPERACIONAL |
| M2021 | CI, documentação e governança | Aplicar M031 no PostgreSQL 16 descartável | CI_SINTETICO |
| M2022 | CI, documentação e governança | Aplicar M031 no PostgreSQL 18 descartável | CI_SINTETICO |
| M2023 | CI, documentação e governança | Testes de idempotência sob mesmo payload | CI_SINTETICO |
| M2024 | CI, documentação e governança | Testes de conflito de idempotência | CI_SINTETICO |
| M2025 | CI, documentação e governança | Testes de múltiplos tenants | CI_SINTETICO |
| M2026 | CI, documentação e governança | Testes de RLS Master | CI_SINTETICO |
| M2027 | CI, documentação e governança | Testes de leitura por membro | CI_SINTETICO |
| M2028 | CI, documentação e governança | Testes de estorno sem aprovação | CI_SINTETICO |
| M2029 | CI, documentação e governança | Testes de reembolso acima do valor | CI_SINTETICO |
| M2030 | CI, documentação e governança | Testes de paginação keyset | CI_SINTETICO |
| M2031 | CI, documentação e governança | Testes de health M2040 | CI_SINTETICO |
| M2032 | CI, documentação e governança | Contract test com migração protegida | CI_SINTETICO |
| M2033 | CI, documentação e governança | Preservar execução da CI frontend | CI_SINTETICO |
| M2034 | CI, documentação e governança | Preservar compilação APK debug | CI_SINTETICO |
| M2035 | CI, documentação e governança | Preservar ZIP código AI Studio | CI_SINTETICO |
| M2036 | CI, documentação e governança | Manter PR #2 Draft e sem merge | CI_SINTETICO |
| M2037 | CI, documentação e governança | Não executar migrations no DB local 5433 | CI_SINTETICO |
| M2038 | CI, documentação e governança | Não executar dinheiro real | CI_SINTETICO |
| M2039 | CI, documentação e governança | Validar OCI e segurança operacional | PENDENTE_OPERACIONAL |
| M2040 | CI, documentação e governança | Aprovação jurídica antes de real-money | PENDENTE_OPERACIONAL |

**Inventário proposto:** 160 IDs; 71 classificados como código/teste de laboratório; 89 como pendências operacionais. Não há declaração de 71 funcionalidades financeiras finalizadas.

## Pendências críticas ainda sem integração

1. Mercado Pago Connect real, credenciais seguras, webhooks e GET authenticated do provedor correto, banco e trilha financeira legalmente válidos.
2. Versão homologável da migração CI para um staging OCI isolado com políticas, testes de carga, backup/restore, observabilidade e aprovações. **Não migrar banco Termux 5433 nesta fase**.
3. Conversão de observações em lançamentos contábeis apenas com provas bancárias verificadas e revisão independente; controle de chargeback, principal, juros, multa e mora sem juros futuros.
4. Recibos e capital conciliados por membro, fechamento e restituições revisados contratual e juridicamente; nada concede quitação real automaticamente.
5. Integração dos painéis Android com informações autenticamente reconciliadas, testes com login de Master/Admin/Membro, extrato e paginação no dispositivo físico.

## Estado obrigatório da governança

PR #2 Draft, sem merge; sem força de push; nenhuma credencial, webhook real, obrigação legal, capital, Pix ou operação real ativada por esta entrega; scripts M031 só em CI e isolados do projeto FRcaixinha 2.2 independente.

## Checagens após CI e sincronização autorizada

1. `git rev-parse --short HEAD` deverá bater com o SHA aprovado.
2. `curl -fsS http://127.0.0.1:8000/api/health/features/m2040` deverá exibir `synthetic_read_routes_registered=false`, `real_payments_enabled=false`, `bank_reconciled=false`.
3. `pg_isready -h 127.0.0.1 -p 5433` somente verifica a instância local; **não comprova a presença da migração 031**, nem deve fazê-la.
4. Todo teste de persistência da nova tabela ocorre unicamente no PostgreSQL 16/18 descartável da CI.