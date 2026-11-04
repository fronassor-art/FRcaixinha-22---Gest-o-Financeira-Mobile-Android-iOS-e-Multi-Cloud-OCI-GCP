# FR Caixinha AI Studio — M531–M600: integrar motores contratuais ao aplicativo

Data: 04/11/2026. Base: `e05ec3c1a4528941e9b80abacc2e6f54d6c64b66`. PR #2 Draft; repositório e banco AI Studio independentes.

## Diretriz consolidada do proprietário

A fase **jurídica vem DEPOIS do desenvolvimento completo, homologação sintética e testes no Oracle OCI**. A ausência de parecer jurídico NÃO bloqueia escrever, testar ou instalar os códigos; NÃO transforma em autorizadas as operações reais com dinheiro de terceiros. Programar todas as regras com versões, evidências e cenários, mas manter modo de testes/DEMO até decisão de ativação comercial.

O Caderno Mestre AI Studio (PDFs versionados no projeto) é autoridade das regras: cláusulas 6.2–6.6 e 8.6, 10.1–10.8, com 147 requisitos rastreáveis. A regra especial das três mensalidades sem quitação é **diferente** de 90 dias de uma única parcela. A retirada voluntária preserva direitos adquiridos e não apaga capital. Variações entre caixinhas precisam de versão de política aceita.

## Entrega técnica inicial do M531

**Backend:** nova rota de consulta com dados do PostgreSQL/RLS; não é motor de punição ou liquidação:

- `GET /api/v1/tenants/{tenant_id}/cycles/{year}/member-risk/me?as_of=YYYY-MM-DD`: somente o membro autenticado na caixinha e seu vínculo ativo.
- `GET /api/v1/tenants/{tenant_id}/cycles/{year}/member-risk/members/{member_id}?as_of=YYYY-MM-DD`: somente administrador daquele tenant, vinculado ao membro selecionado.
- Sem acesso Master, sem leitura de outras caixinhas, sem CPF/email de membros no payload, sem gravação, sem alteração de conta, quota, status ou direitos.
- A resposta contém vencimentos e valores **registrados**, atraso por tempo e sequência de três competências conforme simulação de datas. **Não** supõe que registros pagos sejam comprovantes bancários.
- Resultados sempre apresentam `membership_profit_eligible=null`, `reconciled_principal_cents=null`, `capital_days_weight=null`, `bank_reconciled=false`, `contractual_effect_applied=false`, `financial_closing_authorized=false`.
- Informações cadastrais inconsistentes bloqueiam a resposta com HTTP 503, sem aprovar/concluir nada.

**Frontend:** o demonstrativo anual inclui painel de histórico contratual. Membro consulta somente próprio histórico; administrador seleciona membro a partir da lista autorizada. Data de referência editável para **simulação temporal**, avisos explícitos da ausência de conciliação e respeito à troca de sessão; sem gravar saldos em localStorage.

**Automação:** unitários do backend com matriz de acesso/erros e validação do parser TypeScript; integração de banco real sintético PostgreSQL 16 e 18 testando retornos para perfis, isolamento e sequência registrada. A compilação Android somente acontece se passarem as quatro verificações anteriores.

**Sem migrations nesse pacote.** Os dados da base operacional em Termux 5433 não são alterados. Nenhuma senha, token ou chamada Mercado Pago é adicionada.

## Roteiro de conclusão técnica, por evidência (não fechar artificialmente)

| Frente | O que falta antes de marcar CONCLUÍDO |
|---|---|
| Vinculação ao pagamento bancário | Provider sandbox Mercado Pago, OAuth vendedores, idempotência, webhooks assinados, GET autoritativo, reversões e conciliação transacional |
| Motor de sanções | Histórico temporal durável, evento de bloqueio, direitos preservados, recurso/regularização, regras por tenant versionadas e políticas das obrigações |
| Saída voluntária | Pedido autenticado e auditado; aprovação configurável, restituição, dívidas, direitos adquiridos, encerramento e comprovantes |
| Encerramento de caixinha | Resolução de principal, membros, reservas, passivos, contratos, licenças SaaS e cancelamento separado |
| Fechamento anual | Snapshot por ciclo, resultado líquido, eventos de despesas/perdas, Capital-Dias, exclusões aplicáveis, carteira técnica, 15/85 do proprietário e percentuais próprios de outros tenants |
| Aplicativo | Fluxos de solicitação, revisão, contestação, extratos, demonstrativos e evidências; homologação no dispositivo, sem dinheiro real |
| Infraestrutura OCI | Staging isolado, segredos e ambientes, PostgreSQL, HTTPS, logs, backups/restauração, RLS, filas, monitoramento, testes de carga e segurança |
| Aprovação final | Jurídico após a conclusão técnica e OCI; somente a ativação de dinheiro real depende da aprovação correspondente |

**Importante:** o objetivo final é deixar zero pendências técnicas, mas esse estado não pode ser alegado antes de evidências completas. O novo endpoint não representa conclusão das 147 cláusulas. Os bloqueios de transações reais permanecem intocados, sem comprometer o avanço da implementação.
