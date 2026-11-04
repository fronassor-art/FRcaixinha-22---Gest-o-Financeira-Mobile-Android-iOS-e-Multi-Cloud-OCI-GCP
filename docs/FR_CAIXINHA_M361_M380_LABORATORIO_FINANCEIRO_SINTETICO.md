# FR Caixinha AI Studio — Laboratório financeiro integrado fictício (M361–M380)

Data: 04/11/2026. Base de partida: `0f9ea375ac7481e0cfe8216fc05821e47507a6bc`.
Frente AI Studio Mobile, **independente** do repositório e banco FRcaixinha 2.2. PR #2 segue Draft; main não pode receber merge automático.

## Objetivo
Parar de declarar como "PASS" apenas telas vazias. Executar **SQL real**, **RLS real**, **funções reais do FastAPI** e **cálculos Decimal reais** sobre um conjunto fictício e descartável, com oráculo independente em centavos.
O cenário roda exclusivamente na base `frcaixinha_ci` com PostgreSQL `127.0.0.1:5432` do GitHub Actions.
`FRCAIXINHA_CI_ISOLATED=1` sozinho não basta: DSNs, host, porta, database e papel administrativo são conferidos antes de conectar. O teste recusa o banco Termux `5433`, Oracle, produção, conexões remotas e DSNs diferentes.

**Não há botão para ativar modo fictício no aplicativo operacional.** Este pacote é auditoria automatizada, não carga de teste para a caixinha real.

## Cenário e valores exatos

| Medida | Caixinha fictícia A | Caixinha fictícia B |
|---|---:|---:|
| Administradores | 1 | 1 |
| Pessoas distintas por caixinha (um admin com papel de membro) | 4 | 4 |
| Vínculos (admin + membro) | 5 | 5 |
| Cotas de membro | 4 | 4 |
| Contribuições | 48 (4 × 12) | 48 (4 × 12) |
| Política por cota | R$ 150,00 | R$ 175,00 |
| Valor total devido | R$ 7.200,00 | R$ 8.400,00 |
| Quitações **fictícias** no laboratório | 25 integrais + 1 parcial | 0 |
| Valor ficticiamente pago | R$ 3.825,00 | R$ 0,00 |
| Saldo aritmético em aberto | R$ 3.375,00 | R$ 8.400,00 |
| Transações fictícias no razão | 26 | 0 |
| Débitos e créditos no razão | 382.500 centavos em cada lado | 0 |
| Empréstimos em status SOLICITADO | 1 | 1 |
| Simulação Price: R$ 500,00 | 5 meses a 20% | 3 meses a 15% |
| Total Price esperado | R$ 835,96 | R$ 656,96 |
| Desembolsos reais e Pix reais | 0 | 0 |

**Total das duas caixinhas:** 8 identidades únicas no cenário incluindo 1 Master fictício sem vínculo financeiro, 2 administradores, 10 vínculos de papéis, 8 cotas, 96 contribuições, R$ 15.600,00 previstos, R$ 3.825,00 ficticiamente registrados como pagos, R$ 11.775,00 pendentes e 26 transações balanceadas. O Master sintético é criado **somente no banco descartável**; não se cria Master adicional no banco operacional.

### Rastreabilidade entre motores
- Cada recebimento fictício é associado à **ID da contribuição** em `ledger_transactions.reference_id`, não a um número arbitrário. Para as 26 contribuições marcadas pagas/parciais, o valor pago deve corresponder exatamente aos débitos e créditos contabilizados, centavo a centavo.
- Quatro membros por tenant têm 12 competências; o administrador com papel adicional de membro é uma única pessoa com dois vínculos. Testes diferenciam **quantidade de pessoas** de **quantidade de vínculos**.
- O Master não visualiza razão nem contribuições, membros veem somente seus registros, administradores somente suas próprias caixinhas. Um membro compartilhado entre tenants só vê o contexto atual.
- Dois exemplos de política — R$ 150 e R$ 175 por cota; juros 20% e 15% — garantem que o motor não dependa de um valor global fixo.
- O extrato real por cursor mostra **25 + 1** lançamentos, páginas sem repetição, contabilidade com 26 transações equilibradas; outra caixinha sem transações deve retornar `NO_TRANSACTIONS`.
- Simulação de Price tem débito inicial e juros calculados pelo motor efetivo e conferidos contra valores independentes. Créditos seguem `SOLICITADO`, sem liberação.
- Tudo é criado e removido em CI, sem provedor bancário, credencial de cliente, telefone verdadeiro ou endpoint de pagamento.

## Onde os resultados aparecem
Arquivo: `backend/tests/test_aistudio_financial_lab_integrated_ci.py`.
Workflow: `.github/workflows/validacao-atualizacao.yml`, job de **Migrações e testes de RLS em PostgreSQL descartável**.
Resultado esperado no log do job: `LAB_INTEGRADO_SQL_SINTETICO=PASS`. Se houver discrepância nos valores/links/RLS, o job falha e o macropacote não é aprovado.

## Pendências reais — não encerrar por simulação
1. **Conferência documental**: determinar política efetivamente aprovada para a caixinha inaugural AI Studio. Hoje o aplicativo mostra R$ 100,00 e 2027-12; não sobrepor por R$ 150,00 do teste ou de outro repositório.
2. **Conciliação externa**: sem webhook real de banco/Mercado Pago, PIX real e quitação operacional continuam bloqueados. A quitação fictícia em CI é somente entrada de fixture.
3. **Desembolso/parcelamento/atraso**: provar o motor transacional de emissão, pagamento parcial, mora/multa, estorno, idempotência, atomicidade e auditoria; os dois empréstimos do laboratório são apenas `SOLICITADO`.
4. **Rateio e fechamento**: provar o cálculo Capital-Dias, distribuição exata, 15%/85%, maiores restos e carteira técnica no contrato certo, além de conciliação e dupla aprovação.
5. **SaaS e Oracle OCI**: testes de licenciamento, checkout externo, segredo, criptografia, backups restauráveis, RPO/RTO, deploy, rate limit, monitoração, TLS e aceite jurídico/comercial.
6. **APK com dados fictícios**: requer backend/DB **separado do operacional** (ambiente STAGING) e consentimento para ativar infraestrutura e permissões; não apontar APK de usuário para a base de testes por engano.
7. **SHA em memória**: fingerprints Python no import são úteis, mas não garantem a equivalência integral do processo ao commit Git.
8. **Cursor/snapshot**: paginação keyset elimina OFFSET e evita alguns deslocamentos, mas não garante snapshot imutável entre páginas; investigar alterações concorrentes antes de declarar completude.

## Gates para produção/Oracle
CI 6/6 no SHA final é necessário, mas **não é suficiente** para comercialização. Criar matriz de 147 requisitos com: contrato versionado, teste unitário, integração, staging com dados sintéticos, pentest/segurança, conformidade legal, evidência no APK, teste de restauração, teste OCI e aprovação. Só marcar uma pendência resolvida com evidência verificável. Não remover bloqueios financeiros para "zerar" contagem.

## Orientação operacional
**Não executar o novo arquivo manualmente no Termux**: se a variável de laboratório não existir, será ignorado; se existir, a guarda ainda rejeita PG 5433. Deixar o GitHub Actions criar/descartar a base `frcaixinha_ci`. Nenhuma migration operacional nova foi introduzida; nenhum push ou download para AI Studio é necessário.
