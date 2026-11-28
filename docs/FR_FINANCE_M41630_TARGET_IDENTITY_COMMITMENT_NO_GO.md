# FR Finance M41630–M41633 — autorização vinculada ao destino transacional (NO-GO)

Base operador: M41620 e7d940c4bbd750cc7a141e1bf42b58abb8ce34c3, M40600/M40941 PASS_SOURCE_ONLY_NO_GO. Branch autorizada e PR #2 Draft. Documentos mestres V2.3 de 26/11/2026; matriz 330 IDs/2310 etapas intacta.

## Implementação e rastreabilidade

- CP26-0061 / CTM-07 e TEC-09: fase adicional em backend/tests/m41150_fastapi_rls_context_pg18_disposable.py. Desafio SQL anterior ao ticket, compromisso de identidade vinculado ao desafio do destino, função v5 e reserva de destino no mesmo transaction commit da emissão. Sem autorização para alterar esquema real.
- CP26-0062 / CTM-08: revogação de acesso direto v4 e reserva antiga na fixture; validação de sessão, escopo, expiração e consumo. Provas de destino alternativo, rollback e corrida de duas conexões; RLS de leitura e replay após término de transação.
- CP26-0257 / TENANT_RLS: os testes usam somente PG18 descartável existente, não constituem prova adversarial em staging no banco definitivo.
- TEC-12: backend/tests/test_m41150_fastapi_rls_context_ci.py verifica sintaxe Python, invariantes de ordem e marcadores de teste; workflow existente M41150 executa ambos. Resultados novos ainda não atestados.

Histórico: c92a8a5770d9a5096a11caa0131df5cea118665b implementou a fase; 88adad51836149bd02d6b653efc5afa7638fbf81 corrigiu substituição indevida de âncoras regex durante montagem do texto; d7f6d4ecf002e9e424835da49bcf012faa035010 acrescentou verificações offline. Não suprimir falhas nem promover execuções antigas ao novo SHA.

## Limites e aceite pendente

A fixture pai possui owner, credenciais e material sintético; não demonstra custódia independente. Captura de autorização no mesmo destino, disponibilidade, cancelamento e recuperação operacional, revogação efetiva de sessão no protocolo novo, retenção e identidade real permanecem pendentes. A API FastAPI continua com o protocolo anterior e os seis GET não foram integrados à nova emissão. Não é correção operacional de M40570/M40730. Issue #5 aberta. Exigir CI exata geral 7/7, prova específica, APK debug, revisão e aceite independente antes de promover qualquer capacidade. Nenhum arquivo SQL de migração alterado; DDL exclusivamente dentro do teste descartável. Nenhuma conexão ao banco original, restart, reload, migração, merge ou alteração de flags.

M40840=NO_GO; M40930=HTTP503; ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; COMMUNICATIONS_REAL=OFF; PRODUCTION=BLOCKED.

## Continuidade M41635–M41637

M41634 falhou no teste offline por procurar search_path no corpo em vez do cabeçalho SQL; M41635 (0de07595226e3e446b4af1d133e7ee9172703d53) preservou a verificação e obteve 35/35 offline e PG18 descartável PASS no run 46138465895. Primeira página de workflows: 100/100; CI integral, geral e APK não atestados nesta consulta.

M41636 (2bedd599af2cc6b1d973c5cd09d9852d950fd022) estende CP26-0061/0062/0257 e TEC-09/12 com prova de geração obsoleta, revogação antes da emissão, após reserva e após instalação de capacidade. Exige ausência de ticket/reserva indevida, ausência de capacidade para ticket revogado e limpeza transacional do pool; não restaura sessão revogada. M41637 (b8f5dc78c33feeb49119ffa09e7a1b40afd563ec) adiciona contrato offline. CI do novo conjunto e aceite pendentes; nenhum ID ou etapa promovido. O protocolo real continua não integrado; custódia independente e staging continuam pendentes. Sem alterações SQL de migração, banco original ou flags.
