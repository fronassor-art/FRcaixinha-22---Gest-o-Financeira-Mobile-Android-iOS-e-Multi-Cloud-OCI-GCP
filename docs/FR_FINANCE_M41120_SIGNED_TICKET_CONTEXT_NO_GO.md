# FR Finance M41120 — contexto assinado do ticket (NO-GO)

Base M41110 f35bb505bfb82925c2b117a80187ec2aac4987e7. CP26-0061 / CTM-07 e CP26-0062 / CTM-08. Matriz 330 IDs / 2.310 etapas preservada.

Fixture PG18 existente: geração monotônica muda com usuário, papel, tenant ou revogação. Emissor v2 assina digest, tenant, nonce, validade, escopo, usuário, papel e geração, valida sessão sob bloqueio FOR SHARE, reutiliza o emissor histórico internamente e persiste fotografia do contexto. Validade limitada à prova e sessão. O bind revalida fotografia após consumo, sem expor a resposta financeira interna do gateway histórico; capability compara geração. Emissão v1 e consumo legado deixam de ser executáveis diretamente pelos papéis auth/app no fixture. Runner histórico M40700 permanece intacto.

Testes: adulteração de papel, usuário, escopo e geração; nonce repetido; ticket antigo após troca de papel e retorno; prova antiga negada; emissão nova legítima; ACL. Regressões M41050–M41110 preservadas.

Limites: lookup do signatário é do owner sintético de CI, não autenticação FastAPI. HMAC e segredo compartilhado sem custódia independente; alterações de vínculo ou suspensão fora da sessão ainda requerem solução; isolamento de snapshot e corrida de escrita versus revogação não atestados. Sem integração real, migração de produção ou aprovação M40840/M40930. CP26-0061/0062 PENDING_INDEPENDENT_EVIDENCE. Issue #5 aberta. Meta 30/11 é preparação OCI, não autorização real.

ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
