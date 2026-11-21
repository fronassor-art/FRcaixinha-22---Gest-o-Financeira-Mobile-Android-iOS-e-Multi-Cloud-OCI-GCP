# M21500 — Laboratório Pix TESTE, execução isolada antes da OCI

Objetivo: fechar a lacuna entre ter o arquivo AGE do token e verificar a Orders API de TESTE do Mercado Pago. **O laboratório não liga o backend financeiro nem serve usuários.** Preparado em código; execução autenticada deve ocorrer no Termux do operador, não no GitHub Actions.

## Referência oficial

Mercado Pago Orders API / Pix, teste APRO: https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/integration-test/pix

O teste oficial usa POST /v1/orders, total_amount 50.00, Pix, payer.first_name APRO e uma credencial do painel TESTE; depois consulta GET /v1/orders/{id}. O endpoint é o mesmo usado por produção. **O prefixo APP_USR não comprova sozinho que um token é de teste.** Confirmar a aba TESTE do painel antes de executar.

## Fluxo seguro

1. Atualizar a branch AI Studio, mantendo PR #2 em Draft; não misturar com FR 2.2 independente.
2. Confirmar token cifrado existente em ~/.config/frcaixinha-aistudio-mobile/mp-sandbox-credentials.json.age. Nunca imprimir, enviar ou colar o token.
3. Inspecionar o plano local sem rede, sem banco e sem criar pedido.
4. Somente após verificar que o token foi retirado da aba TESTE, executar **uma** order sintética de R$ 50,00, com confirmação digitada. O teste grava previamente UUID de idempotência e referência em arquivo privado (0600), e nunca reenvia um POST de forma automática.
5. Consultar GET autenticado pelo identificador criado, com validação de valor, método, referência e identidade da order. Registrar apenas status sintéticos, sem QR nem corpo de resposta.

No Termux, com a árvore sincronizada e limpa:

    cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
    git pull --ff-only
    export AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)"
    python3 backend/scripts/aistudio_mp_credentials_local.py audit
    python3 backend/scripts/aistudio_mp_pix_sandbox_lab.py prepare
    python3 backend/scripts/aistudio_mp_pix_sandbox_lab.py run-test
    python3 backend/scripts/aistudio_mp_pix_sandbox_lab.py status

Quando pedir confirmação, digitar CONFIRMO_PIX_TESTE_50 **somente** após conferir TESTE no painel. O AGE poderá pedir sua senha no próprio terminal. O script nunca a recebe por argumento ou variável de ambiente.

## Bloqueios automáticos

- SHA/branch incompatível, árvore alterada, flags de Pix real ativadas, token/AGE ausente ou arquivo inseguro.
- Ausência da confirmação interativa; token que não respeite o envelope de TESTE; recusa de campos extras; permissões incorretas.
- Resposta com live_mode true, valor diferente, método não-Pix, referência divergente, mais de um pagamento, IDs incompatíveis, status fora da lista e JSON malformado.
- HTTP 302/401/429/500, falha de transporte e timeout: **não tentar novo POST com outra idempotency key**. Com resultado desconhecido, procurar a referência no painel de teste e conciliar manualmente a identidade antes de pensar em reabrir um caso.
- O estado privado conserva um caso por instalação. Para repetir testes, criar procedimento auditado de encerramento do caso; nunca apagar o arquivo e executar de novo impulsivamente.

## O que o teste não prova

GET aprovado não é liquidação bancária independente. Nenhuma contribuição é baixada; nenhum empréstimo é desembolsado; nenhum webhook é publicado; nenhum lançamento, Pix real ou fechamento é autorizado. Em particular, ainda faltam OAuth Connect por tenant, Vault da OCI, endpoint HTTPS, webhook persistente, settlement, RLS em staging, homologação APK e habilitação comercial de Money Out.

## CI

A suíte backend/tests/test_m21500_mp_pix_sandbox_lab_ci.py usa somente MockTransport, sem rede nem credenciais; cobre construção APRO, redirecionamentos/429/timeout sem retry, chaves duplicadas, mismatch de valores/status, permissão 0600, replay, token e ausência de efeito financeiro.

Próxima etapa após execução autenticada: anotar somente M21500_PROVIDER_ORDER_STATUS, M21500_PROVIDER_PAYMENT_STATUS e M21500_CASE_PHASE; nunca anexar QR, credenciais, arquivos AGE ou payload integral a issues, logs ou chat.
