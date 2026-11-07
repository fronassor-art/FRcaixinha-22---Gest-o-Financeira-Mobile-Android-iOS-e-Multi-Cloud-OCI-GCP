# AI Studio M2801–M2900 — webhook HTTPS verdadeiro, inbox staging

## Código para receber notificações oficiais

- `backend/app/mp_webhook_staging_runtime.py`: cria rota FastAPI real POST `/integrations/mercadopago/webhook`. Checa HTTPS, tamanho, JSON sem campos repetidos, query `data.id`/tipo, `x-request-id`, HMAC `x-signature` (10 ou 13 dígitos no timestamp), seller, escopo da caixinha, event id, e ações payment/mp-connect. Sem data sensível em retorno. Rejeita `live_mode=true` por padrão; modo live de RECEBIMENTO pode ser liberado separadamente, **sem autorização financeira**. **Rota não é registrada em main.py** até configuração/secret/store/HTTPS.
- `backend/app/mp_staging_postgres.py`: repositório para somente leitura de seller autorizado e inclusão idempotente de evento; exige banco `frcaixinha_staging`, login técnico dedicado `frcaixinha_mp_webhook_ingest` e função SQL definida. Nenhuma ligação com banco Termux 5433.
- `backend/staging_migrations/034_mp_signed_webhook_staging_only.sql`: SQL de infraestrutura **não aplicado**. Exige role dedicada, superusuário de implantação e opt-in `frcaixinha.mp_staging_authorized=1`. Tem vínculos do seller / secret OCID sem plaintext, inbox imutável com replay idêntico e conflito bloqueado; flags rígidas no banco (`payment_marked_paid=false`, `bank_reconciled=false`, `ledger_written=false`, `financial_closing_authorized=false`). Necessita revisão manual de DBA/IAM e testes de migração em staging descartável **antes de aplicar**.
- `backend/tests/test_m2900_webhook_server_ci.py`: suíte local que cria servidor FastAPI falso com HTTPS, assinaturas verdadeiras criadas com segredo fictício, bloqueios e replay; nenhum request vai ao Mercado Pago.

## Infraestrutura necessária para conectar depois

1. Staging OCI com Compute/contêiner privado, acesso de saída ao PSP restrito, endpoint HTTPS público com certificado TLS e proteção de origem/rate limiting. O blueprint privado M2600 **não oferece isso ainda**.
2. Identidade da aplicação Mercado Pago criada no portal e URLs de callback/notifications cadastradas. Cada vendedor/tenant autoriza Connect; armazenar seu secret/token no serviço OCI apropriado.
3. Login técnico dedicado ao webhook com mínimo privilégio e leitura do SecretBundle pelo Instance Principal. Segredo de assinatura do webhook pertence à **aplicação**, jamais deve ser enviado pelo cliente.
4. Resolver de seller deve consultar vínculo criado **somente após OAuth confirmado**. O request recebido nunca escolhe tenant nem OCID de segredo.
5. Analisar o plano Terraform e executar migração staging somente com autorização expressa, backup cifrado, controle de acesso e evidências operacionais. Em caso de indisponibilidade do inbox a rota responde 503 para permitir nova tentativa.
6. Consumidor de inbox fará GET autenticado via seller correto; status `approved` + assinatura validada NÃO são liquidação. Reconciliar extrato autêntico e ledger antes da baixa; não habilitar Pix, fechamento ou saques com este pacote.

## Estado

No GitHub: mecanismos disponíveis como código; PR #2 permanece Draft. No Termux: nenhum SQL staging aplicado, nenhuma infraestrutura OCI criada, nenhuma integração oficial Mercado Pago ativa. A Issue #3 continua pendente de homologação real.

Fontes: https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications e https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation
