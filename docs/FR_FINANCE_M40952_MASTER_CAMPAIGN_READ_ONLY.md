# FR Finance M40952 — painel de campanhas SaaS durante NO-GO

O painel Master passa a indicar claramente o bloqueio real de gravação,
publicação e cancelamento. Os três controles ficam desativados e os handlers
recusam requisições de escrita mesmo se acionados por outro caminho da UI.
O preenchimento local por conta continua disponível, com a política de
persistência existente, sem criar campanhas no servidor.

A lista Master mostra a situação temporal da campanha (rascunho, cancelada,
agendada, dentro da vigência ou encerrada), calculada somente para exibição
pelo relógio do aparelho; datas ambíguas/inválidas não são confirmadas.
Não constitui prova de elegibilidade, licença, status de provedor ou autorização.
O backend preserva a revisão histórica e recusa justificativa vazia disfarçada
de espaços e revisões não inteiras nos testes sintéticos de transição.
Nenhuma alteração em SQL112/113, regra de preço, campanha existente,
PostgreSQL original, serviço ou pagamento. O guard M40930 permanece obrigatório.

M40951 + M40952 exigem CI no SHA final antes de sincronização.
`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`;
`PRODUCTION=BLOCKED`.
