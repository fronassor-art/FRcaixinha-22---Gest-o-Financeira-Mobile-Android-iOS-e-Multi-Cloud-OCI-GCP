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

## Continuidade M41639–M41641 — interface de destino antes da emissão

M41639 (82e17159bdddc649c5b89f27d7fb012b31023582) implementa em backend/app/m41150_fastapi_rls_context.py um contrato explícito FRF-M41630-v1: sessão verificada, nonce gerado no servidor, transação read-only, identidade SQL, desafio pré-ticket separado por domínio, emissão e reserva pelo provedor, desafio do ticket, vínculo, leitura de claims e limpeza. Versão desconhecida ou método ausente retorna 503 antes do pool; recusa, erro ou desafio inválido não retorna ao protocolo legado. Compatibilidade com fixtures anteriores somente sob o guard não produtivo; o provedor padrão continua ausente. Nenhum provedor real instalado. M41640 (083456912ff43bcf9af556562d3a43ad3ed29f0d) acrescenta testes offline positivos e negativos, cancelamento e limpeza. M41641 (71e90c523201e91d8762a5a5aa1a28cb321cb04a) conecta o contrato a uma fixture v5 exclusivamente descartável, exercita seis GET, confere compromisso consumido e reserva única por nonce, indisponibilidade 503 e limpeza. CI e aceite destes novos commits ainda pendentes. CP26-0061/0062/0257 e TEC-09/12 preservados, sem promoção. Custódia, autenticação não sintética, staging e provedor real permanecem NO-GO. Nenhuma migração ou alteração de flags.

## Continuidade M41643–M41644 — bloqueio M40840 com provedor injetado

M41643 (582cd8c7c941) alinhou a execução geral e a compilação ao SHA exato. Após retorno M40600/M40941 do operador, o Termux confirmou HEAD=582cd8c7c941, branch/repositório fixos, árvore rastreada limpa e PLAN=VALIDATED_NO_GO. Nenhuma migração, escrita no banco ou reinício foi realizado.

M41644 (8a2da69f55acb61f62a1a55153a2fe183d71bb90) acrescenta regressão em backend/tests/test_m41150_fastapi_rls_context_ci.py, vinculada a CP26-0061/0062/0257 e TEC-09/TEC-12. Sete combinações negativas verificam que, com provedor target-first injetado, modo production/desconhecido/ausente, flag real ligada ou flag obrigatória ausente, a dependência financeira responde HTTP 503 antes de chamar o provedor ou abrir o pool. A resposta permanece genérica.

## Evidência M41644

- Execução específica M41150: offline e PostgreSQL 18 descartável PASS, run 46142284544.
- CI integral no SHA M41644: 155/155 workflows PASS; validação geral 7/7 PASS e compilação/verificação do APK debug assinado PASS, run 46142284425.
- Artefato frcaixinha-ai-studio-debug, SHA-256 afc06e214556f144486f5c3ae4e3c354f2654e19d0ba4384a664d800858db063; expira em 05/12/2026.
- Diff M41644: somente o teste acima; sem alteração de código runtime, arquivos SQL de migração ou schema. Nenhum acesso ao PostgreSQL original, escrita, migração, restart ou reload.

O teste prova o guard de software sob configurações inválidas; não prova custódia independente, identidade real, staging ou homologação externa. M40570/M40730, issue #5, M40840 NO-GO e M40930 HTTP 503 permanecem abertos. Preservar matriz 330 IDs/2.310 etapas, flags reais OFF e PRODUCTION=BLOCKED. Nenhum requisito/gate é promovido por CI.
