# FR Finance — Aditivo técnico M40060

Complementa `docs/FR_FINANCE_ADITIVO_M40050_INDICE.md` sem alterar o Caderno Mestre, o Contrato Técnico ou os manifests selados em M39100.

**Referência:** `docs/FR_FINANCE_M40060_API_READONLY_LACUNAS_REVISAO.md`.

Integra, no FastAPI principal, dois endpoints GET privados para consulta de pendências de política de revisores dos caixas exclusivos, com sessão autenticada, segregação de patrimônio e titularidade do administrador confirmada por SELECT RLS. Nenhum poder de aprovação, lançamento ou pagamento é criado. Testes específicos de integração são inteiramente sintéticos e não acessam os bancos originais.

**Checkpoint recebido:** M40050 `7036a33` sincronizado no Termux. **M40060:** publicação e regressão na PR #2 Draft antes da próxima sincronização.

`M40060_LOCAL_MIGRATIONS=NONE`; `M40060_ORIGINAL_DATABASE_WRITES=NONE`; `M40060_FASTAPI_RESTART=NONE`; `M40060_REAL_APPROVAL=FALSE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
