# FR Finance AI Studio — M35400–M35800 | Licença SaaS vinculada ao GET

Checkpoint de origem: M35300, commit `c5210dc99c2b873bceb21108425c06f6491cb122`.

## Avanço do pacote

Este supermacropacote integra o módulo de readback M35300 ao registro de
cobrança já persistido, em modo estritamente de leitura.

- Requer sessão autenticada de **Master** sem tenant ativo.
- Usa a conexão PostgreSQL transacional autenticada via RLS para consultar
  `saas_payment_intents`, `saas_subscription_preparations` e a versão
  imutável do preço fixada na preparação.
- O valor é recalculado em centavos por `Decimal`. Incompatibilidade
  entre preço fixado e intenção bloqueia antes da chamada ao provedor.
- Valida relações de tenant, administrador, versão de oferta e finalidade
  exclusiva `MERCADO_PAGO` da plataforma; sem consultar o razão interno.
- Encaminha dados de origem RLS ao adaptador existente de GET, somente
  em **modo de teste** e com governança exigida pelo próprio adaptador.
- Confere valor, moeda, referência, conta recebedora, ambiente e estornos
  com respostas simuladas por `httpx.MockTransport`.
- Repetição não realiza escritas e gera digest repetível para os mesmos
  campos verificados.

## Limitações de produção

O serviço é interno: **nenhum endpoint público, cobrança, receita,
conciliação, nova licença ou ativação de membro** foi criado.
Uma conexão injetada ou tag de origem não comprova, por si só, origem
autêntica: o futuro runtime deverá usar `get_rls_db_connection`
real, segredo protegido no Vault, evidência do provedor independente,
trilha persistente auditável, aprovação separada e lock transacional
durante a eventual ativação.

As variáveis de ambiente `AI_STUDIO_REAL_*` em testes foram impostas
apenas por `pytest.monkeypatch`; isto **não autoriza produção**.
Não aplicar migrações ao PostgreSQL `5433`. Catálogo SQL permanece 105.
O Mercado Pago real e Pix real permanecem **desativados**.

## Próxima fronteira operacional

Validar OCI pública e PostgreSQL de staging, DNS/HTTPS, Vault/IAM,
permissão comercial do Mercado Pago e readback realmente autenticado.
Só então preparar reconciliação SaaS em worker segregado, idempotência
transacional e evidência tripla. A migração 046 continua candidata não
aplicada. A migração 064 é exclusiva da CI descartável.
