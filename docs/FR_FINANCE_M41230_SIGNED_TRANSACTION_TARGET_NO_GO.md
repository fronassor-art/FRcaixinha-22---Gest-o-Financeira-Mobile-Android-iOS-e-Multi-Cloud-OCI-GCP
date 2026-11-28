# FR Finance M41230 — prova criptográfica do destino da autorização (NO-GO)

Base M41220: de66f01f4c2fc0c43c7b9bfd5616820eba79fb91, Termux PASS_SOURCE_ONLY_NO_GO informado pelo operador. CP26-0061 / CTM-07, CP26-0062 / CTM-08, CP26-0257 / TENANT_RLS, TEC-09, TEC-12; 330 IDs e 2.310 etapas preservados; Issue #5 PENDING_INDEPENDENT_EVIDENCE.

O binder descartável exige HMAC-SHA256 separado por domínio FRF-M41230|v1, vinculado ao hash do ticket, tenant, PID, virtual XID e início da transação (microssegundos UTC). Verifica formato, janela, lock ativo e prova antes de consumir o ticket. O binder anterior de cinco argumentos não é criado. O binder histórico sem vínculo continua para regressões, incapaz de habilitar current_claims_v4. Chave de teste existente, sem segredo novo no aplicativo.

Testes: prova ausente/incorreta, substituição de ticket/tenant/tempo e segunda transação ativa, autorização legítima após negativas e regressões M41220, seis rotas HTTP. CI precisa comprovar resultados. Não modifica SQL de migração, catálogo autoritativo ou provider padrão.

Limites: assinador sintético usa a chave de teste existente no mesmo processo de fixture; não prova custódia independente, integridade do processo nem impede um emissor comprometido de assinar outro destino. Binder histórico pode consumir ticket sem autorização de ledger (risco de indisponibilidade). M40570, M40730, M40840, M40930 e M41180 continuam; não ativar provider.

ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; MIGRATIONS=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
