# FR Finance — Aditivo técnico M40080

Complementa `docs/FR_FINANCE_ADITIVO_M40070_INDICE.md`. Preserva as evidências e documentos selados M39100.

**Relatório técnico:** `docs/FR_FINANCE_M40080_RUNTIME_SNAPSHOT_REVOGACAO_CI.md`.

Novidade: endpoint GET sem dados privados que mostra impressão digital dos arquivos **no instante da importação do FastAPI**; verificador nativo Termux somente leitura para distinguir checkout Git de processo carregado, com prova do proprietário via M39800 quando disponível. Testes CI PostgreSQL 18 descartável exercitam revogação de sessão e troca de titularidade entre requisições.

Sem atestado de Git SHA executado, sem autorização financeira, sem acesso a bancos originais, sem reinício do FastAPI. PR #2 mantém-se Draft.
