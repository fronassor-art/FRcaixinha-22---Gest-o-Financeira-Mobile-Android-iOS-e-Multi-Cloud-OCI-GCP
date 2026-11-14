# FR Caixinha AI Studio M19300 — migrações locais 028–030

Os originais backend/migrations/028-030 são CI-only. As cópias em backend/local_migrations/028-030 acrescentam uma guarda para PG18 Termux (banco exclusivo, porta 5433, papel owner) ou CI explicitamente descartável. Não há SQL de dinheiro real ou alteração de memberships, rateio e ledger.

028: solicitações de saída e inadimplência (somente eventos de revisão); 029: eventos de revisão e contestação append-only; 030: rodadas de pedido com idempotência e lock. A sequência instala duas tabelas novas (34 → 36) e troca a função sandbox, em uma única transação.

Comandos sob o SHA homologado:
- `AI_STUDIO_APPROVED_SHA=SHA40 bash backend/scripts/aistudio_lifecycle_local_028_030.sh audit`.
- Somente após PASS, `AI_STUDIO_APPROVED_SHA=SHA40 AI_STUDIO_APPLY_LIFECYCLE_028_030=YES bash backend/scripts/aistudio_lifecycle_local_028_030.sh apply`. Requer confirmação, backup com age e senha guardada.
- `AI_STUDIO_APPROVED_SHA=SHA40 bash backend/scripts/aistudio_lifecycle_local_028_030.sh verify`. Sem comprovação local, sem homologação do APK.

Nenhuma migração 034–041 deve ser aplicada via scripts CI/OCI no Termux. Todos os fluxos de pagamentos, sanções, fechamento, Pix, conciliação e envios externos seguem bloqueados.
