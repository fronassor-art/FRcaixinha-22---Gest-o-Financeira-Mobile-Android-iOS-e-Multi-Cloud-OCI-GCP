# FR Finance M41270 — prova do destino inclui desafio SQL (NO-GO)

Base M41260 b9f21efd9565c75fb0919e58bdcd5d5422de0531; retorno M40600/M40941 PASS_SOURCE_ONLY_NO_GO confirmado pelo operador. CP26-0061/CTM-07, CP26-0062/CTM-08, CP26-0257/TENANT_RLS, TEC-09, TEC-12. Preservar matriz 330/2310 e issue #5.

O assinador descartável autentica o digest do ticket, tenant, PID, virtualxid, início de transação em microssegundos e o desafio SQL recebido, sob domínio FRF-M41270 v1. O binder verifica a assinatura nesse novo domínio e a autenticidade do desafio SQL independente antes do consumo. Não há fallback para o domínio M41230. O desafio é obrigatório no protocolo do worker. O contrato FastAPI permanece fail-closed, sem provider real.

Provas propostas: HMAC canônico, alteração isolada de desafio, desafio ausente/malformado, rejeição de assinatura antiga ainda com chave correta, composição de prova e desafio diferentes, rejeição de assinatura com chave emissora, seis rotas, concorrência, isolamento e regressão da CI descartável. A aprovação depende dos runs do SHA publicado.

Limites: o processo pai ainda pode solicitar assinatura de outro destino; o assinador não valida sozinho a chave SQL; autenticar o desafio não equivale a exclusividade do ticket, custódia independente ou atestação Linux do runtime real. O consumo único existente permanece, sem nova alegação de proteção contra captura do pai privilegiado. Não altera SQL110–113 nem corrige GUC/ACL no banco original. Não altera regras financeiras.

M40840=NO_GO; M40930=HTTP503; MIGRATIONS=NONE; ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
