# FR Finance M41260 — prova SQL do destinatário da autorização (NO-GO)

Base M41250 e5c4f15ff19a7d05ba34f7df7fd7856eac3f04ab; M40600/M40941 PASS_SOURCE_ONLY_NO_GO confirmado pelo operador. CP26-0061/CTM-07, CP26-0062/CTM-08, CP26-0257/TENANT_RLS, TEC-09, TEC-12. 330 IDs e 2.310 etapas preservados; Issue #5 aberta.

O protótipo descartável acrescenta chave exclusiva gerada pelo PostgreSQL, não lida por emissor, assinador, autenticação ou app. read_target_challenge emite HMAC com domínio independente FRF-M41260, digest do ticket, tenant, PID, virtualxid e timestamp da transação própria, somente login descartável autorizado e transação read-only. O binder exige assinatura existente E prova SQL antes do consumo do ticket. FastAPI exige a prova na mesma transação; erro/ausência = HTTP 503, sem fallback. Interface do provider recebe target_challenge. Nenhum provider real configurado.

Testes: ACL negativa, transação de escrita negada, assinatura válida sem prova ou prova de outro destino negada, mudança de timestamp/tenant, regressões do M41250, seis rotas, concorrência, isolamento e limpeza. CI deve comprovar. Apenas DDL dentro do fixture PG18; nenhuma migração candidata ou original alterada.

Limites: login app capturado pode pedir prova da própria transação; não é atestação do processo Linux, nem prova de posse exclusiva do ticket; pai privilegiado e proprietário SQL continuam na fronteira de confiança. Não remove GUC histórico, não comprova custódia independente nem habilita produção. M40840/M40930 e demais gates permanecem. Exigir revisão independente da arquitetura, staging, identidade do serviço, backup/restore e autorização específica para ACL/migração real.

ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; MIGRATIONS=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
