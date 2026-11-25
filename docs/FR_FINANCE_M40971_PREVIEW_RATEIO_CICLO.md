# FR Finance M40971 — preview de rateio por ciclo

## Escopo desta entrega

O pacote conecta a base de lucro líquido realizado (M40970) ao cálculo Capital-Dias V2 existente. Exige uma política apresentada como aceita, congelada e vinculada ao mesmo tenant, ciclo e janela; o percentual é informado explicitamente em pontos-base e não há valor padrão. O cálculo mantém o fechamento exato em centavos, a regra de maiores restos e o desempate pelo `membership_id` já implementados em Capital-Dias.

A camada produz apenas um preview em memória e um fingerprint SHA-256 determinístico dos dados de entrada e do resultado. Ela não autentica o aceite, não verifica a autenticidade das linhas financeiras, não grava snapshot, não autoriza beneficiários nem efetua pagamentos. O campo de aceite e as referências continuam sendo declarações fornecidas pelo chamador.

## Regras preservadas

- Receita precisa estar recebida, conciliada e dentro da competência/ciclo; principal, recebíveis não pagos, juros futuros e valores excluídos não compõem lucro.
- O percentual administrativo é explícito, entre 0 e 10.000 bps (precisão técnica de 0,01 p.p. do contrato); o complemento é destinado ao conjunto dos membros.
- Política, tenant, ciclo e janela devem coincidir. O carimbo de congelamento não pode anteceder o aceite.
- Admin + pool dos membros = lucro distribuível. Se não houver pesos elegíveis, o pool dos membros fica pendente e não é transferido ao Admin.
- Soma das parcelas atribuídas + pendência = pool dos membros.
- A saída declara `executionAuthorized=false`; aprovação, persistência de snapshot, ledger, conciliação e liquidação continuam em etapas separadas.

## Verificação

O teste cobre rateio de centavos e desempate estável, soma conservada, política recusada ou fora do escopo/ciclo, percentual fora dos limites, congelamento anterior ao aceite, linha financeira em tenant alheio, pool sem pesos e digest repetível/diferente quando a entrada muda.

## Evidência que não resulta deste código

Esta implementação é fonte de preview. Não demonstra aceites reais, ledger autoritativo, persistência, autorização, infraestrutura de staging, runtime carregado, integração PSP, homologação Android, aprovação jurídica ou liberação de produção. Nenhuma migração SQL é criada neste pacote.