# FR Finance M41100 — revogação durante reuso de pool asyncpg (NO-GO)

## Escopo e rastreabilidade

M41100 verifica no fixture PostgreSQL 18 descartável que revogar uma sessão
invalida uma capability que havia acabado de autorizar uma leitura. O teste usa
o pool asyncpg de tamanho um e o mesmo backend físico antes e depois da
revogação. O proprietário do fixture revoga a sessão em uma conexão sintética
separada enquanto a conexão de aplicação está devolvida ao pool.

Requisitos relacionados: CP26-0061 / CTM-07 e CP26-0062 / CTM-08. Os 330 IDs e
2.310 etapas não mudam. Este teste automatizado não constitui prova independente
de identidade em staging nem aceite de produção.

## Cenário executado pelo runner

1. Cria uma sessão e uma capability de membro sintéticas com validade curta.
2. Empresta uma conexão asyncpg, instala a capability dentro de transação e
   confirma a claim e somente a linha pertencente ao membro.
3. Devolve a conexão ao pool; a conexão do fixture revoga a sessão.
4. Reempresta o mesmo backend, instala a capability antiga e tenta forjar os
   GUCs legados como Master. Espera zero claims e zero linhas por RLS.
5. Confere limpeza de papel/capability após a transação e o reuso.

O runner exige marcadores M41100, DSN fixo 127.0.0.1:55439, banco descartável
fr_m40700_disposable_ci, ambiente GitHub Actions e flags reais OFF. O acesso
administrativo limita-se ao fixture descartável para revogar uma linha
sintética.

## Limites

- Rotas de produção, serviço e credenciais reais: não integrados.
- SQL de produção, schema e migrações: nenhum alterado.
- Banco autoritativo 127.0.0.1:5433/frcaixinha_aistudio_dev:
  ORIGINAL_DATABASE=NOT_ACCESSED.
- Escritas do ensaio: apenas no fixture PostgreSQL 18 descartável.
- Reinício ou reload do FastAPI/PostgreSQL: nenhum.
- CP26-0061 e CP26-0062: PENDING_INDEPENDENT_EVIDENCE.
- PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF.
- PRODUCTION=BLOCKED; Issue #5 permanece NO-GO.

A CI avaliará este cenário antes de qualquer sincronização do novo SHA.

## Marcadores registrados pelo pacote

ACTIVE_BEFORE_REVOKE; REVOKED_REBORROW; SAME_BACKEND.
ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE.
