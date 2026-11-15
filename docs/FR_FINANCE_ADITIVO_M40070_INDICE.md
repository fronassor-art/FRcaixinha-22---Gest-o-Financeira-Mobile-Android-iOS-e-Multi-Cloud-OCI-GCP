# FR Finance — Aditivo técnico M40070

Complementa `docs/FR_FINANCE_ADITIVO_M40060_INDICE.md`, mantendo intactos o Caderno Mestre, Contrato Técnico e hashes M39100.

**Referência:** `docs/FR_FINANCE_M40070_FASTAPI_AUTH_PG18_DESCARTAVEL.md`.

Testa os endpoints GET do M40060 por HTTP na API original, com caminho de autenticação real do código e RLS PostgreSQL 18 descartável do GitHub Actions. Os dados e as duas funções SQL de autenticação são fixtures CI, não evidências de políticas reais. Nenhum banco local, provedor, revisão ratificada, saque, Pix ou pagamento são acessados.

Checkpoint local: M40060 `73da599`, sincronizado. PR #2 em Draft; nenhuma ativação financeira.
