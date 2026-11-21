# FR Finance M40930 — contenção de gravações Master e redesenho SQL (NO-GO)

Data: 20/11/2026. Base: M40929 `eb4b238` na branch `atualizacao-ai-studio-9b46a63187`, PR #2 Draft. Não é aprovação de produção nem autorização de migration.

## Correção aplicada no **código-fonte** do FastAPI real

1. Adicionado `backend/app/m40930_master_write_no_go.py`, uma dependência FastAPI que **sempre devolve HTTP 503**. Não possui flag, modo de produção liberável, variável de ambiente nem credencial de exceção.
2. Obrigatória como *dependência da própria rota*, anterior à obtenção de conexão, nas três escritas Master atuais identificadas: `POST /api/v1/master/license-prices`, `POST /api/v1/master/saas-promotions/draft` e `POST /api/v1/master/saas-promotions/transition`. Alterar preço SaaS, rascunhar, publicar e cancelar promoções ficam indisponíveis **até uma substituição arquitetural auditada**.
3. Leitura Master, simulação de transição, preflight sem escrita e rotas de membros não foram liberadas nem modificadas. A rota break-glass permanece negada. A trava M40840 de pool financeiro em produção **não foi removida nem alterada**.
4. A suíte histórica `test_m39067_master_saas_promotions_ci.py` substitui explicitamente essa dependência apenas no objeto de app do teste com banco inteiramente fictício. Isso não é uma chave de bypass do app publicado. Em condições reais, não existe override de runtime.
5. A nova suíte `test_m40930_master_write_no_go_ci.py` verifica as três rotas por AST, 503 sob vários modos/flags, ausência de execução do corpo, regressão M40840 e ausência de dependência SQL/rede na trava. CI específica `frfinance-m40930-master-write-no-go-ci.yml`.

**Impacto funcional intencional**: depois de uma eventual atualização do FastAPI para esse código, o Android/cliente poderá receber 503 nessas três operações Master. Não sincronizar nem reiniciar serviços automaticamente. O protótipo M40923–M40929 não foi conectado ao backend real.

## Por que é apenas contenção

M40928 demonstrou a violação com **três credenciais SQL + Bearer Master**. M40929 comprovou que SO_PEERCRED e modo 0600 não distinguem processo malicioso sob o mesmo UID. A implementação do guardião em CI usa nonce em memória, entrega uma capacidade opaca pela conexão Unix e não prova o controle do PostgreSQL real. Um ator com owner/superuser SQL pode alterar ACL, RLS, função ou trigger. Nem token Master, flag de CI, assinatura no gateway ou ACL de socket suprem a falta de autorização imposta **pelo servidor SQL ou por uma fronteira independente de confiança**.

## Arquitetura-alvo — pendente de implementação e revisão

| Fronteira | Requisito de prova |
|---|---|
| Aplicação pública | Sessão Master verificável, MFA, revogação, vínculo explícito a ação/corpo/tenant/revisão. Não possuir DSN issuer/guardian, owner, superuser, BYPASSRLS ou chave de assinatura. |
| Serviço de autorização independente | Identidade de serviço própria, credenciais isoladas, verificação de assinatura e política fora do controle do gateway, registro durável de nonce/replay, expiração, chave rotacionável, revisão humana para ações críticas. SO_PEERCRED pode ser um sinal complementar, nunca a única prova. |
| Emissor e custódia SQL | Privilégios mínimos; emissor não consegue criar selo; guardião não consegue aprovar sem prova independente; o aplicativo não consegue inserir diretamente em tabelas protegidas, conceder acesso ou trocar de papel. Não concentrar as três credenciais no mesmo domínio de comprometimento. |
| PostgreSQL | Funções SQL assinadas/revisadas com `search_path` fixo, RLS forçada, owners NOLOGIN, revogação de CREATE/TEMP e SET ROLE/INHERIT perigosos, ACL/DEFAULT PRIVILEGES auditadas, checagem transacional de uso único. Substituir identidade GUC falsificável por contexto autoritativo ligado à sessão, não apenas renomear variável. |
| Auditoria e host | Separação por usuário/serviço/host quando apropriado, proteção de segredos, Vault/KMS, logs imutáveis, telemetria, rota de revogação e isolamento em caso de falha. Ninguém deve obter múltiplos segredos por acesso ao mesmo processo/runner. |

## Provas obrigatórias para substituir a contenção

- Verificar o inventário completo de `SECURITY DEFINER`, `SET ROLE`, GUCs, DSNs, privilégios de emissor, guardian, app, tenant e Master. Focar M40570 e M40730.
- Em PostgreSQL 18 **descartável** de staging, tentar capturar separadamente e em conjunto credenciais de gateway/app/emissor/guardian, token Bearer, socket, capacidade, nonce, assinatura e chave pública. Provar que nenhum caminho de escrita não assinado ou sem revisão é possível sob o modelo de ameaça aprovado.
- Provar transação única para autorização, escrita e auditoria; replay, concorrência, cancelamento, timeout, indisponibilidade, troca de tenant, revogação e crash recovery.
- Validar separadamente cada rota real, cada role e sua SQL, sem mock de autorização; executar pentest independente e evidências operacionais na infraestrutura de staging.
- Só depois: propor migrations revisadas com checksum, backup e restore demonstrados, rollback, autorização expressa para ambiente original, branch/release gate e homologação física.

**Estado:** este pacote **não** corrige M40570 nem M40730 e não prova custódia independente, portanto permanece **NO-GO**.

`PR_2=DRAFT`; `MAIN=NO_MERGE`; `ORIGINAL_PG18_CONNECTIONS=NONE`; `LOCAL_DB_WRITES=NONE`; `MIGRATIONS=NONE`; `SERVICE_RESTARTS=NONE`; `TERMUX_SYNC=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
