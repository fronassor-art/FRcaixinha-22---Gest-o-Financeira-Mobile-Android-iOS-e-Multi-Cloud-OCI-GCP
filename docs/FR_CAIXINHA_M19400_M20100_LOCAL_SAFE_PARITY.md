# FR Caixinha AI Studio — M19400–M20100: oito equivalentes locais seguros

Estas migrações **não são cópias** dos SQL OCI/CI `staging_migrations/034–041`; são estruturas de **homologação local sintética**, nomeadas separadamente. Os SQL originais permanecem exclusivos de CI/OCI. As novas tabelas não possuem acesso de leitura/escrita para funções do aplicativo, nem trabalhadores financeiros, e não ativam operações bancárias.

Cada arquivo possui guarda que aceita somente (i) cluster Termux PG18 AI Studio porta 5433, usuário frc_ai_owner, PGDATA exclusivo; (ii) CI descartável frcaixinha_ci com superuser postgres e flag ci. RLS habilitado e obrigatório, nenhum policy SELECT/INSERT para frcaixinha_app_role/auth_role.

| Local | Tabela sintética | Contexto, sem efeito financeiro |
| --- | --- | --- |
| 034 | `local_m034_webhook_evidence` | `034_local_webhook_evidence.sql`, histórico de ensaio isolado |
| 035 | `local_m035_pix_dryrun` | `035_local_pix_dryrun.sql`, histórico de ensaio isolado |
| 036 | `local_m036_orders_inbox` | `036_local_orders_inbox.sql`, histórico de ensaio isolado |
| 037 | `local_m037_order_evidence` | `037_local_orders_read_evidence.sql`, histórico de ensaio isolado |
| 038 | `local_m038_order_reservation` | `038_local_orders_reservations.sql`, histórico de ensaio isolado |
| 039 | `local_m039_reconciliation_hold` | `039_local_reconciliation_holds.sql`, histórico de ensaio isolado |
| 040 | `local_m040_incident_audit` | `040_local_incident_audit.sql`, histórico de ensaio isolado |
| 041 | `local_m041_notification_outbox` | `041_local_notification_outbox.sql`, histórico de ensaio isolado |

Estas tabelas não equivalem a integração real com Mercado Pago, a autorização de transferências, leitura do provedor, webhook verificado, conciliação efetiva nem entrega real de notificações. Essas funcionalidades continuam bloqueadas e necessitam desenvolvimento de serviços/segurança próprios, apesar de a estrutura de ensaios estar migrada no Termux.

O instalador incremental deverá exigir: 36 tabelas preexistentes com 028–031 e RLS; backup cifrado validado; confirmação; transação para 034–041; verificação pós-migração de exatamente 44 tabelas e oito tabelas sem privilégio de app, com flags financeiras impedidas. O GitHub Actions deve executar estes arquivos no PostgreSQL descartável 16/18, sem confundir o resultado com a instalação no telefone.
