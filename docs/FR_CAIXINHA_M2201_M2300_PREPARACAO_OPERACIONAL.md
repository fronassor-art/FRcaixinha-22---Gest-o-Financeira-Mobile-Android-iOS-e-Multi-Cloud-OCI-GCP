# FR Caixinha AI Studio — M2201–M2300: início da resolução operacional

Base: `73028e3a396bb0c3060fde39bfffff4ee14b03ae` (M2200), 04/11/2026. Projeto **AI Studio**, não FRcaixinha 2.2. PR #2 **Draft**, sem merge.

## O que foi implementado

1. `backend/app/mp_operational_preflight.py`: pré-importação **local e somente leitura** de CSV de `settlement_report` do Mercado Pago (modelo oficial com `;`), validando identidade `USER_ID` do recebedor, `SOURCE_ID`, referências externas, moedas BRL, datas com fuso, limites de tamanho, registros duplicados, UTF-8, números exatos sem float, bruto + tarifa (negativa) = líquido. Movimentos diferentes de SETTLEMENT e discrepâncias ficam `*_REVIEW`. Hash SHA-256 para identificar bytes de origem, **não** para atestar autenticidade.
2. Validador de HMAC-SHA256 de webhook, com manifest `id:<data.id>;request-id:<x-request-id>;ts:<ts>;`, comparação em tempo constante, verificação de idade, rejeição de IDs malformados, valores repetidos e alterações da mensagem. **Não** registra endpoint de webhook, usa segredo apenas em memória e não processa eventos.
3. `backend/tests/test_m2300_operational_preflight_ci.py`: regressões parametrizadas para múltiplas divergências financeiras, fraude CSV, recebedor errado, duplicatas, replay e falsificação de assinatura.
4. `/api/health/features/m2300`: informa apenas o contrato e bloqueios; não consulta arquivo, banco, tokens, HTTP externo ou saldo.
5. CI passa a executar a suíte nova, sem migração local/CI e sem alterar APK ou PostgreSQL.

## Matriz: progresso seguro sobre itens antes pendentes

| Controle M2200 | Avanço técnico M2300 | Ainda necessário |
|---|---|---|
| M2057–M2058, M2134 | Parser determinístico de exportação CSV obtida manualmente | Permissão de acesso, geração e obtenção autenticada do relatório por tenant, verificação de proveniência |
| M2076–M2078, M2132–M2133 | Conferência exata de bruto/tarifa/líquido, marcação das exceções | Provedor GET autenticado, identificação das tarifas reais, conciliação de saldo e confirmação independente |
| M2095, M2135 | CSV de outro `USER_ID` é recusado | Consentimento e vinculação persistida sellerID ↔ tenant, revogação/renovação |
| M2123, M2137, M2139 | Verificação pura HMAC; não registra endpoint e não registra segredo | HTTPS, webhook inbox persistente, replay durável, configuração de chaves, auditoria e homologação externa |
| M2113–M2116, M2171–M2176, M2200 | Nenhuma alteração no APK neste pacote | Homologação manual de navegação, redes, três perfis e instalação |
| M2141–M2160 | Nenhuma autorização automática | Ledger persistente, estornos, comprovação bancária, validação jurídica/contábil, fechamento anual com auditoria |
| M2161–M2170, M2177–M2180 | Sem deploy nem segredos | OCI staging, TLS, vault, backups, observabilidade, LGPD, rollback e auditoria externa |

**Não converter `ARITHMETIC_MATCH_UNVERIFIED` em quitação**. Exportação manual pode ter sido alterada e não prova banco. HTTP 200 do webhook, assinatura válida, GET aprovado, ou relatório individual isolado não bastam para disponibilizar caixa, baixa, empréstimo, Pix ou fechamento.

## Próxima etapa necessária para fechar pendências operacionais

- Integrar OAuth Connect por empresa com consentimento explícito e tokens armazenados em cofre; sem repassar senha/token ao chat ou ao GitHub.
- Criar binding seller ↔ tenant imutável e revogável, processamento assíncrono de webhook em inbox de banco, deduplicação persistente e GET autenticado, com bloqueio do uso de live_mode para testes.
- Agendar/recolher extratos autorizados e comparar com ledger imutável, com reconciliação por operação e conta antes de contabilizar ou baixar.
- Homologar APK em dispositivo, testes de UI dos três perfis e infraestrutura de staging com backups/restauração e logs sem dados privados.
- Só após evidências independentes e aprovações específicas avaliar qualquer ativação financeira; não habilitar por mudança em health ou flag de teste.

## Referências técnicas

- Relatório `settlement_report`: https://www.mercadopago.com.br/developers/pt/docs/links-and-debts/additional-content/reports/account-money/api
- API de relatórios: https://www.mercadopago.com.br/developers/pt/reference/reports/overview
- Assinaturas de notificação: https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications
- OAuth authorization code: https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation
