# FR Finance AI Studio — M38070–M38089 | Histórico persistido bloqueia reenvio inseguro

**Origem:** checkpoint M38069, commit d96e74a, 1.240 testes Python no Termux. Somente FR Finance AI Studio.

## Lacuna tratada
O classificador sintético M26500 já colocava SMTP aceito, bounce e timeout incerto em estados sem reenvio automático. Entretanto, um operador futuro podia classificar uma **nova** tentativa como falha anterior ao envio sem consultar um recibo existente em outra tentativa do mesmo evento, e então voltar a considerar novo lease. O M38070 cria um segundo limite de decisão, que inspeciona a visão *completa* dos recibos e do estado terminal gravado para o outbox.

## Entrega — M38070–M38089
- Contrato imutável `PersistedOutboxEvidence` com evento, lease, lista completa de tipos de recibos sintéticos e estado terminal.
- `decide_delivery_with_outbox_evidence` combina o classificador M26500 com o histórico: um recibo CI_SMTP_ACCEPTED impede reenvio e **não** prova entrega; CI_BOUNCE exige revisão manual; timeout incerto ou contradições resultam em quarentena.
- Históricos inválidos, UUID de evento ou lease divergentes, tipos desconhecidos, listas indevidas e estados de entrega falsos geram `DecisionBlocked`.
- Apenas histórico sem recibos e sem estado terminal permite **candidatura** a outro lease, quando a evidência de preflight prova que nenhuma submissão começou e o limite de tentativas não foi alcançado. Nunca autoriza automaticamente uma chamada SMTP.
- Regressões em matriz de tentativas, resultados persistidos, inconsistências, validação de schema e ausência de mutações.

## Limites críticos
A visão de histórico `PersistedOutboxEvidence` **precisa ser obtida por um worker confiável**, com autenticação, RLS/segregação e bloqueio transacional que abranja o evento e os leases anteriores. O código Python não consulta o banco, não verifica autenticidade de objetos Python e não substitui as funções SQL existentes de staging. Não se deve preencher os campos a partir de HTTP, navegador ou remetentes de e-mail. Esse pacote não implementa um worker real, não grava recibos, não envia notificações, não habilita contas nem comprova posse da caixa postal.

Não há migrations novas, alterações no PostgreSQL original do Termux, chamadas à OCI ou operações Pix. `REAL_EMAIL=OFF`, `REAL_ACTIVATION=OFF`, `REAL_PIX=OFF`, `PRODUCTION=BLOCKED`.

## Testes
```sh
PYTHONPATH=backend python -m pytest -q -p no:cacheprovider backend/tests/test_m38070_persisted_outbox_resend_ci.py backend/tests/test_m26500_delivery_decision_ci.py
```
