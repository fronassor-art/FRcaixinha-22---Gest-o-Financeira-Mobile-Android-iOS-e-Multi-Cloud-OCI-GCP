# FR Finance M41240 — separação da chave de destino e assinador descartável (NO-GO)

Base M41230 f8a1f96bf84256bb4225313a8a628ff1a2a598b8; retorno real M40600/M40941 PASS_SOURCE_ONLY_NO_GO. CP26-0061/CTM-07, CP26-0062/CTM-08, CP26-0257/TENANT_RLS, TEC-09, TEC-12. 330 IDs e 2.310 etapas preservados. Issue #5 PENDING_INDEPENDENT_EVIDENCE.

O fixture PG18 usa m41050.target_verifier_secret, separado da chave emissora m40700.verifier_secret. O processo filho CI gera chave aleatória, transfere uma vez ao proprietário privilegiado do fixture para provisionamento e assina somente digest do ticket, tenant e identidade de transação por pipes herdados privados, com frame limitado, timeout, ambiente allowlist sem DSN, sem listener, e verificação do processo pai. O binder não aceita fallback à chave emissora. A chave de destino não é distribuída ao código FastAPI.

Testes: chave distinta, ACL de autenticação/aplicativo negada, assinatura pela chave emissora rejeitada, regressões M41230, ausência do verificador, perda do assinador com HTTP 503 e limpeza do pool, protocolo offline e bootstrap consumido uma vez. CI deve confirmar. A operação DELETE e DDL são exclusivamente descartáveis. Nenhum SQL de migração alterado.

Limites: o pai privilegiado vê a chave durante provisionamento e pode solicitar assinaturas; os pipes e PPID não demonstram identidade atestada do FastAPI ou conexão SQL, nem isolamento de UID/root ou custódia independente real. HMAC simétrico permanece compartilhado com verificador SQL; não configura Vault/IAM, não autoriza serviço real. O processo filho não é um serviço paralelo persistente. O provider padrão continua ausente, M40570/M40730/M40840/M40930/M41180 e M40929 continuam. Próximo: prova independente da origem da sessão/identidade do destinatário em staging, com aprovação humana antes de qualquer alteração de ACL, custódia ou runtime.

ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; MIGRATIONS=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
