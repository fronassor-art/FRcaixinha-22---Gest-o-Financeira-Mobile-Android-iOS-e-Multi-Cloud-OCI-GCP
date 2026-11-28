# FR Finance M41000 — calendário da primeira caixinha, prévia source-only

Base: branch atualizacao-ai-studio-9b46a63187, HEAD b7bfca2c13f6dd7796b725c4953e2e8bcffee224. PR #2 permanece Draft.

## Escopo

Registrar no aplicativo Master, sem vincular a tenant, o calendário expressamente informado para **a primeira caixinha do proprietário**. Não altera o padrão global, não cria obrigação e não altera dados de ciclo existentes.

| Item | Data/valor |
|---|---|
| Início e primeira contribuição prevista | 10/12/2026 |
| Vencimento mensal | Dia 10 |
| Última contribuição prevista | 10/11/2027 |
| Quantidade de datas mensais | 12 |
| Encerramento e pagamento final informado | 20/12/2027 |
| Fuso de exibição | America/Belem |

As 12 datas são geradas de dezembro de 2026 a novembro de 2027. Não há valor por cota nem quantidade de cotas por membro; a prévia não inventa esses valores.

## Limites importantes

O dia 20/12/2027 é mostrado como a data de encerramento/pagamento final informada. O corte diário do Capital-Dias exige decidir se esse dia entra na base. A implementação mantém capitalDaysEndExclusive nulo e não calcula rateio, porque os motores financeiros exigem uma janela explícita e exclusiva. A data será escopo somente da primeira caixinha depois de vinculada ao tenant e aceita nos instrumentos corretos.

A jornada apresentada separa:
1. convite do administrador pelo Master;
2. cadastro, revisão do Contrato A e assinatura SaaS pelo administrador;
3. revisão/aceite do Contrato B e configuração da caixinha;
4. convites, aceites do Contrato B e contribuições dos membros.

O Contrato A (licença FR Finance) e o Contrato B (adesão à caixinha) são instrumentos e pagamentos diferentes. A V2.2 deste checkpoint é minuta para aprovação; o manifesto dos modelos permanece DRAFT_ONLY e acceptance_enabled=false. Caderno Mestre e Contrato Técnico orientam o produto, mas não substituem instrumentos comerciais individualizados. O cartão Master não afirma que a data já foi transferida ao tenant ou ao convite.

## Evidência de desenvolvimento

- src/services/firstCaixinhaCalendarDraftV1.ts: valida datas civis e gera vencimentos mensais.
- src/components/FirstCaixinhaCalendarDraftPanel.tsx: prévia interna Master-only, sequência e bloqueios.
- src/tests/m41000_first_caixinha_calendar_draft_ci.test.ts: calendário positivo, datas inválidas, cadência e flags sem execução.
- Nenhuma alteração SQL/API; nenhum banco acessado/escrito, migration, sync Termux, reinício ou reload; nenhum convite ou pagamento real.
- PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED.

## Próxima dependência para vinculação real

A inclusão do calendário e Contrato B no convite/tenant requer semântica do corte, valor e número de cotas, contrato publicável aprovado, oferta de licença preenchida e desenho versionado de persistência/RLS. Só então a API e o tenant carregarão a política; migração será etapa separada e não autorizada por este pacote.
