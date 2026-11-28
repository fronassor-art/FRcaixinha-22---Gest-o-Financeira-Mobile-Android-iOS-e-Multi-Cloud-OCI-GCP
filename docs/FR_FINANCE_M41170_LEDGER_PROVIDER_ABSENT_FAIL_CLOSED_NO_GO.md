# FR Finance M41170 — fail closed nas leituras do ledger sem provedor (NO-GO)

**Data:** 26/11/2026  
**Branch:** `atualizacao-ai-studio-9b46a63187`  
**Checkpoint Termux confirmado antes deste pacote:** `ce1da0cddebc6d02bcde35dd2ea77b76d494d936`; M40600 source-only e M40941 `PASS_SOURCE_ONLY_NO_GO`.

## Escopo e rastreabilidade

M41170 altera somente a dependência das seis rotas GET de leitura do ledger já cobertas por M41160. O pacote se vincula a **CP26-0061 / CTM-07** e **CP26-0062 / CTM-08**. Mantém os 330 IDs, as 2.310 etapas e os sete estágios de evidência; não promove estado da matriz nem representa aceite independente.

## Problema e correção

M41160 havia mantido, quando o provedor de capability estava ausente, um fallback para `get_rls_db_connection`. Essa dependência preservava a rota legada baseada em contexto GUC e deixava estas leituras condicionadas ao bloqueio M40840.

M41170 remove o fallback. Sem provedor independente, cada rota de leitura do ledger responde **HTTP 503 antes de abrir pool ou conexão**. Com provedor presente, permanece o fluxo existente: sessão verificada, papel e tenant canônicos, ticket de uso único, capability vinculada e transação PostgreSQL `READ ONLY`; RLS ainda restringe as linhas. A ausência de provider não é convertida em autorização nem em conexão de compatibilidade.

## Prova em CI descartável

A execução M41150/60/70 exercita a aplicação FastAPI real em PostgreSQL 18 descartável. Com estado de provider ausente e sessão sintética válida, verifica 503 nas seis rotas e instrumenta o pool para exigir zero chamadas. Com o provider sintético, preserva a prova das seis leituras, concorrência, isolamento entre tenants, rejeição dos GUCs legados forjados, sessão não verificada, replay de ticket e revogação.

A autenticação e o emissor do teste são sintéticos. A prova não atesta custódia independente, esquema autoritativo, API em execução, Termux/OCI, staging nem revisão externa; CI não promove os estados da matriz.

## Limites e checkpoint

M41170 reduz o caminho de leitura do ledger que ainda recorria ao GUC legado quando faltava provider. **Não resolve M40570 globalmente**, não configura ou homologa emissor/custódia de M40730, não substitui M40840 nem altera o HTTP 503 de M40930. A issue #5 permanece aberta.

```text
M41170_PROVIDER_ABSENT=HTTP_503
M41170_LEGACY_GUC_FALLBACK=REMOVED
M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE
MATRIX_ACCEPTANCE=PENDING_INDEPENDENT_EVIDENCE
M41170_AUTHENTICATION=OVERRIDDEN_SYNTHETIC
M41170_PROVIDER=CUSTODY_NOT_CONFIGURED
ORIGINAL_DATABASE=NOT_ACCESSED
MIGRATIONS=NONE
SERVICE_RESTARTS=NONE
RUNTIME=NOT_RELOADED_OR_ATTESTED
PIX_REAL=OFF
PAGAMENTOS_REAIS=OFF
ATIVACAO_REAL=OFF
PRODUCTION=BLOCKED
NO-GO
```
