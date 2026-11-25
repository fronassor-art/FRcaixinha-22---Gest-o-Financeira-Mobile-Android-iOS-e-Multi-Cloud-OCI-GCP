# FR Finance M40973 — obrigações separadas por papel

## Entrega

O preview explicita três classes em memória: remuneração administrativa, lucro de membro e pool de membros pendente. Se o administrador também estiver listado como membro do ciclo, as duas linhas permanecem separadas. O membership associado ao papel administrativo precisa existir no mesmo cálculo de tenant/ciclo; sem pesos elegíveis, o pool dos membros permanece pendente e não é transferido à remuneração administrativa.

O fingerprint também rejeita números não finitos e referências circulares, mantendo a serialização canônica de campos opcionais já implementada.

## Testes e rastreabilidade

Testes positivos e negativos cobrem administrador-membro, administrador sem membership, membership ausente do ciclo, pool sem pesos, conservação total, número não finito, objeto circular e chave opcional. Relação com Contrato Técnico V2.2 §§10.5–10.8, Caderno §§10.5–10.7 e itens AT-13/AT-14. Nenhum ID ou etapa da matriz 330/2310 é declarado concluído por código ou CI.

## Limites

IDs, aceites e referências continuam fornecidos pelo chamador e não são autenticados. O resultado não é persistido, aprovado nem liquidado; não é ledger autoritativo, staging, homologação real ou autorização humana. A precisão percentual permanece pendente e nenhum percentual padrão é definido. Nenhuma alteração SQL, banco original, runtime, pagamento ou produção.
