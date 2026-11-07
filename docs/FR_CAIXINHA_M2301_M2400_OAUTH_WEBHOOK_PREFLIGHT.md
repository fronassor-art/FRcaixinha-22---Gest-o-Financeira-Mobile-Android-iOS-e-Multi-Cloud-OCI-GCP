# AI Studio M2301–M2400 — preparação OAuth e validação de notificações

**Base M2300:** `86082f1917e875a1f4ffa4de10fcafccdbc4c1c1`.
**PR:** #2 continua Draft. **Sem merge, migrações ou alteração financeira.**

## Entregas implementadas e testadas

- `backend/app/mp_oauth_connect_preflight.py`: estado criptográfico aleatório por tentativa; código PKCE S256; URL de autorização parametrizada com redirect estático HTTPS; ligação à sessão do tenant e ator; janela máxima de dez minutos; rejeição de callback expirado, reutilizado (estado declarado pelo chamador), externo ou de outro tenant; validação conservadora de metadados `seller_id` / `live_mode=false`. Nunca grava token, faz HTTP, autoriza pagamento ou marca o seller como efetivamente conectado.
- `backend/app/mp_webhook_envelope_preflight.py`: análise estrita de JSON, rejeição de campos repetidos, assinatura inválida, modo live, seller de outra caixinha, ID da query divergente do corpo, ação/tipo incompatível, corpo excessivo. O hash do payload identifica bytes recebidos, **não** substitui assinatura, consulta GET, consentimento ou conciliação.
- `backend/tests/test_m2400_connect_webhook_preflight_ci.py`: regressões parametrizadas e negativos. Rota `/api/health/features/m2400` sinaliza estado de projeto sem conectar a serviços.
- CI executa a suíte. **Não se adiciona endpoint de recepção**, nem token store, banco, fila, saque, Pix, lançamento ou baixa.

## Pendências remanescentes da Issue #3

As 87 pendências operacionais M2200 são rastreadas na [Issue #3](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/issues/3).

Os seguintes itens avançam somente em validações preliminares, **não** se encerram: M2094–M2099 (OAuth, vínculo de seller, credenciais), M2121–M2125 (Connect, webhook, inbox persistente, GET), M2135–M2139 (segregação, live_mode, logs), M2164 (cofre ainda não configurado).

## Requisitos antes de ativação real

1. Coleta de consentimento do vendedor e inscrição da aplicação MP, com callbacks HTTPS externos permitidos.
2. Armazenamento de `state`, `code_verifier`, tenant, sessão, nonce, expiração e consumo atômico em banco; apenas hashes quando suficiente.
3. Cofre de segredos isolado por tenant, rotação, refresh token e revogação.
4. Endpoint de webhook HTTPS autenticado, deduplicação persistente e recuperação de falhas; a resposta HTTP não constitui liquidação.
5. GET assinado/autenticado do pagamento no collector correto e comparação com extrato autorizado e ledger.
6. Testes OCI staging + APK instalado + revisão LGPD, contábil e jurídica. Go-live requer autorização específica.

**Nota de política:** a validação pura não pode ser apresentada como OAuth conectado ou como webhook em produção. Dados com `live_mode=true` são recusados nesta etapa.

Documentação oficial: https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation e https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications
