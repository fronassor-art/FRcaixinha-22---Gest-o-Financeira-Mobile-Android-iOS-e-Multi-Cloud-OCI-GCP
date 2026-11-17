# FR Finance M40300 - Reconciliação contratual, migracoes e criterios de aceite

## Identidade documental

Caderno Mestre vigente: docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md. Contrato Técnico vigente: docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md. A matriz CP20261114 tem 57 exigencias originais, 49 aditivos, 147 clausulas historicas de outro projeto, 20 gates tecnicos, 7 externos e 50 AT, total 330. Historico FR Caixinha 2.2 nao vira contrato atual automaticamente.

**Este aditivo de engenharia nao altera as regras ja aprovadas:** cota inicial com minimo de R$150 escolhida pelo administrador, formula de referencia de 15% administrador e 85% membros sobre lucro elegivel, 90 dias de atraso distinto de tres competencias, credito especial como oportunidade nao vinculante sujeita a analise/contrato, preferencia de canais sem habilitar envio real, preco SaaS mensal/anual independentes. Variantes de percentuais existentes no oraculo sao testes de matematica e nao nova regra comercial.

## Divergencias DR-01 e DR-02

- SQL110/111: aplicacao controlada relatada em 12/11/2026, verificacoes M39032-M39034; documentacao anterior que cita pendencia pode estar desatualizada, mas o estado live nao foi reatestado neste pacote.
- SQL112/113: aplicacao relatada em 13/11/2026, M39068/M39069; mesma ressalva sobre proveniencia e evidencia.
- M40240: catalogo read-only do PostgreSQL 18 original preparado, mas ainda NAO EXECUTADO devido bloqueios anteriores no Git (SHA literal errado; avancos OCI). Nao confundir isso com perda de banco ou alteracao de senha.
- M40300: alterações em fonte FastAPI, regras puras, fronteira Android, CI e documentos, sem novas tabelas, novas contas, schema SQL, nova migracao ou implantacao cloud.

A reconciliacao live requer PG18 original ativo, identidade confirmada, hashes de esquema, backup e log de migracoes. Se o Android encerrar Termux, verificar status de PG e FastAPI primeiro; servidor desligado NAO prova corrupcao. Nenhum SQL e executado neste aditivo.

## Criterios dos quatro pontos

- Seguranca: matriz negativa de tenant/role, destinatario, grant, membro ativo e ciclo; cliente nao envia bearer para URL inesperada. Testes sinteticos aprovados nao atestam RLS live.
- Credito: validade/ciclo, opt-in/out, interesse/recusa, rejeicao de repeticao, sem criacao de divida, reserva, notificação ou Pix reais.
- Financeiro: Price amortiza exatamente, capital dias completo no ciclo sem ignorar evento tardio, previsoes deterministicas, duplicatas bloqueadas, capital nao registrado como lucro e conservacao 15/85 em cenarios de referencia.
- Android: sessao antiga nunca remove a nova; UI nao fica ocupada ao trocar de contexto; rede off nao gera repeticao de POST nem alegacao de perda do PostgreSQL; compilacao web executada; aparelho fisico ainda nao homologado.
- Aceite e release: 20 gates live, 7 externos, 50 AT e VM nao habilitados por CI; PR #2 continua Draft, main intacta, nenhum go-live.

Revisao juridica e regulatoria continua separada. Nao houve alteracao de contrato assinado, troca de banco ou processamento de dados pessoais.
