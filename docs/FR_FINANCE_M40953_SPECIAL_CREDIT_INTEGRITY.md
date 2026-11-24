# FR Finance M40953 — integridade de Crédito Especial e Extraordinário

Continuidade M40952, exclusivamente na branch FR Finance. Consentimento
promocional aceita somente booleano JSON explícito; prazo de simulação
exige inteiro exato. Título e mensagem de campanha são normalizados e
recusados quando vazios ou com caracteres de controle. Simulação exige
vínculo de membro do tenant e política de prazo válida. A oportunidade
expõe a menor validade entre campanha e autorização.

O cliente valida a resposta da simulação: identidade da autorização,
principal, prazo, taxa, valores em centavos, total e indicadores de
aprovação/reserva/desembolso estritamente falsos. Não há concessão de
crédito ou criação de contrato por esta resposta. Valores Decimal
serializados pelo FastAPI são normalizados somente após verificação.
Testes novos nas suítes M39020 existentes; CI obrigatória no SHA final.

SQL110/111, dados, configuração do celular, provedores e runtime intocados.
PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
