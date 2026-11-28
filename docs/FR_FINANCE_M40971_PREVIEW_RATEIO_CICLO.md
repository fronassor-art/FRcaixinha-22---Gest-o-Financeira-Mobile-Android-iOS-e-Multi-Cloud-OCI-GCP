# FR Finance M40971 — preview de rateio por ciclo

## Escopo desta entrega

O pacote conecta a base de lucro líquido realizado (M40970) ao cálculo Capital-Dias V2 existente. Exige uma política apresentada como aceita, congelada e vinculada ao mesmo tenant, ciclo e janela; o percentual é informado explicitamente em pontos-base e não há valor padrão. O cálculo mantém o fechamento exato em centavos, a regra de maiores restos e o desempate pelo `membership_id` já implementados em Capital-Dias.

A camada produz apenas um preview em memória e um fingerprint SHA-256 determinístico dos dados de entrada e do resultado. Ela não autentica o aceite, não verifica a autenticidade das linhas financeiras, não grava snapshot, não autoriza beneficiários nem efetua pagamentos. O campo de aceite e as referências continuam sendo declarações fornecidas pelo chamador.

## Regras preservadas

- Receita precisa estar recebida, conciliada e dentro da competência/ciclo; principal, recebíveis não pagos, juros futuros e valores excluídos não compõem lucro.
- O código aceita explicitamente 0–10.000 bps (0,01 p.p.) apenas como representação técnica proposta no TEC-04. O Caderno V2.2 §16.4-D mantém a precisão percentual pendente de aprovação expressa; este pacote não transforma a proposta em regra vigente nem autoriza aplicá-la a ciclos reais.
- Política, tenant, ciclo e janela devem coincidir. O carimbo de congelamento não pode anteceder o aceite.
- Admin + pool dos membros = lucro distribuível. Se não houver pesos elegíveis, o pool dos membros fica pendente e não é transferido ao Admin.
- Soma das parcelas atribuídas + pendência = pool dos membros.
- A saída declara `executionAuthorized=false`; aprovação, persistência de snapshot, ledger, conciliação e liquidação continuam em etapas separadas.

## Verificação

O teste cobre rateio de centavos e desempate estável, soma conservada, política recusada ou fora do escopo/ciclo, percentual fora dos limites, congelamento anterior ao aceite, linha financeira em tenant alheio, pool sem pesos e digest repetível/diferente quando a entrada muda.

## Evidência que não resulta deste código

Esta implementação é fonte de preview. Não demonstra aceites reais, ledger autoritativo, persistência, autorização, infraestrutura de staging, runtime carregado, integração PSP, homologação Android, aprovação jurídica ou liberação de produção. Nenhuma migração SQL é criada neste pacote.

## Rastreabilidade e estado dos requisitos

- Requisitos vigentes relacionados: Caderno Mestre V2.2 §§10.1–10.4, 16.2 e 16.4-D; Contrato Técnico V2.2 §§4.3–4.4 e 10.1–10.6, TEC-04; itens AT-13 (base e pesos por tenant) e AT-42 (conservação e desempate de centavos).
- A matriz histórica no repositório contém CM-08 / CP26-0008 (15%/85%) e HIST-10.4 / CP26-0194. Esses textos são mantidos como histórico; não são aplicados pelo novo preview quando conflitam com a decisão vigente de percentual livre por administrador.
- Precisão de percentual permanece decisão pendente. O limite técnico testado em M40971 não fecha essa decisão; o cálculo é evidência de fonte/CI, não aceite contratual nem homologação de produção.
- Este pacote cobre implementação e teste automatizado do preview. Aceite de política real, staging, identidade/autorização, persistência de fechamento, reconciliação, autorização humana, liquidação e produção continuam pendentes nas etapas de evidência/aceite da matriz. Nenhum ID ou etapa da matriz foi declarado concluído.
