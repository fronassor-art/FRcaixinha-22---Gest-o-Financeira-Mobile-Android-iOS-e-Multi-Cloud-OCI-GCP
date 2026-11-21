# FR Finance — M40700: prova HMAC vinculada à requisição (protótipo, NO-GO)

**Escopo:** PostgreSQL 18 descartável no GitHub Actions; sem novas migrations, rotas reais, comunicação financeira real, reinícios de processos ou conexão ao PostgreSQL do Termux. PR #2 permanece draft.

## Falha reconhecida no M40690

O token Bearer bruto não chega ao SQL no M40680, mas o digest SHA-256 chega ao papel de autenticação e é suficiente para emitir novos tickets. Se o digest e os privilégios SQL do autenticador vazarem, um atacante pode fabricar tickets sem conhecer o Bearer. O M40690 comprovou esse risco — não é um problema de replay apenas do ticket, mas da **capacidade de emitir tickets repetidamente**.

## Experimento M40700

O protótipo cria uma prova HMAC-SHA256 de uma requisição concreta, vinculada a:

- domínio/versão FRF-M40700 v1;
- digest da sessão;
- tenant de destino;
- nonce aleatório de uso único;
- instante de expiração, limitado a 30 segundos;
- escopo fixo READ_ENTRIES.

Uma chave sintética de 256 bits existe na memória do emissor confiável de testes e numa tabela protegida, acessível somente ao proprietário da função SECURITY DEFINER. O papel autenticador não recebe a chave nem privilégios de SELECT nessa tabela. A função de emissão valida a prova antes de emitir um ticket, verifica sessão ativa, tenant e vínculo, e consome nonce por INSERT ON CONFLICT DO NOTHING para recusar replay. O papel autenticador perde EXECUTE na antiga função M40680 que aceitava apenas digest. O papel financeiro permanece sem EXECUTE na nova função de emissão.

A prova adversarial cobre: digest sem assinatura, assinatura com chave errada, tenant/nonce/expiração/escopo manipulados, expiração vencida ou distante, tentativa de reutilização do nonce, segundo consumo do ticket e revogação da sessão entre emissão e consumo. Tudo é fictício; nenhuma credencial é impressa na saída.

## O que isso NÃO resolve

O resultado restringe especificamente o atacante que possui apenas digest e privilégios do papel autenticador, mas **não** é um desenho pronto para produção:

1. Quem comprometer o emissor confiável, a chave HMAC compartilhada ou a função proprietária poderá gerar novas provas. A chave está no banco no fixture, protegida por ACL; não é hardware não exportável nem há rotação/gestão de Vault.
2. Assinaturas HMAC e tickets ainda atravessam SQL; podem vazar em logs, query diagnostics, extensões, memória e ferramentas de observabilidade. A comparação de strings na função não foi certificada contra temporização.
3. Uma prova válida capturada antes de sua primeira utilização ainda poderá sofrer corrida; a unicidade do nonce reduz replay após o primeiro uso, mas não garante prova de posse nem elimina interceptação.
4. O teste não demonstra autenticação real do FastAPI, caminho de escrita financeira, segurança de sessão entre múltiplos nós, atomicidade de todas as transações, revogação concorrente já iniciada ou retirada de privilégios das rotas existentes.
5. A vulnerabilidade de falsificação de GUC por SQL arbitrário no backend financeiro real continua **NOT_REMEDIATED**.

Não copiar o SQL fictício diretamente para migrações reais. Antes de um rollout seriam obrigatórios isolamento arquitetural do emissor, KMS/Vault ou solução equivalente de chave, rotação, auditoria independente de SQL/ACL e telemetria, modelagem de transações e segurança ponta a ponta.

## Portões de segurança

- M40700_DIGEST_ALONE_AND_TAMPERED_ATTESTATION_DENIED — escopo experimental
- M40700_NONCE_REPLAY_AND_TICKET_REPLAY_DENIED — escopo experimental
- M40700_SIGNER_KEY_COMPROMISE=NO_GO
- M40700_SIGNATURE_DB_PARAMETER_LOGGING=NOT_REMEDIATED
- M40700_HMAC_VERIFY_TIMING=NOT_ATTESTED
- M40700_EXISTING_GUC_SPOOF=NOT_REMEDIATED
- M40700_PRODUCTION_INTEGRATION=NOT_ACTIVATED
- M40700_ORIGINAL_PG_5433=NOT_ACCESSED
- M40700_LOCAL_DB_WRITES=NONE
- M40700_LOCAL_MIGRATIONS=NONE
- M40700_SERVICE_RESTARTS=NONE
- PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED

**A CI verde não implica autorização para produção.** A PR #2 permanece rascunho, sem merge.
