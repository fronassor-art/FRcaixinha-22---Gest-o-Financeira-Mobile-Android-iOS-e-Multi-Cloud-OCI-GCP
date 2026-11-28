# FR Finance M40972 — fingerprint com campos opcionais

## Problema e correção

O envelope de preview serializava todas as propriedades de um objeto. Um evento de contribuição válido não contém `reversesEventId`, campo que só se aplica a reversões. A serialização anterior tentava codificar essa propriedade ausente como valor de topo e recusava o fingerprint, embora o cálculo do Capital-Dias aceitasse o evento.

M40972 passa a omitir propriedades de objeto com valor `undefined`, mantendo ordenação canônica de chaves. Em arrays, posições indefinidas seguem a representação JSON `null`; números não finitos são recusados. A entrada financeira permanece validada pelo cálculo existente antes da geração do digest.

## Testes

O teste M40972 usa uma contribuição confirmada sem `reversesEventId`, verifica peso Capital-Dias e conservação do pool, repete o fingerprint e compara o digest após reordenar as chaves dos mesmos objetos. Não simula autenticação, persistência, aprovação ou liquidação.

## Rastreabilidade e limites

- Continuidade source-only de Capital-Dias e do envelope de preview M40967–M40971; relação funcional com Caderno Mestre V2.2 §§10.3–10.4 e itens AT-13/AT-42.
- Matriz CP20261114/2310 não é reescrita e nenhum requisito ou etapa é marcado concluído por este patch. Os registros históricos de 15%/85% continuam sem aplicação quando conflitam com o Caderno V2.2 atual; a precisão percentual permanece pendente.
- Nenhum SQL, API operacional, banco, segredo, runtime ou pagamento é alterado. A CI apenas valida código e teste isolado.
- Fingerprint é integridade determinística da entrada apresentada, não assinatura nem prova de autenticidade do aceite.
