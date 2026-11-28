# FR Finance — M40710: auditoria de assinatura capturada e fronteira da chave HMAC (NO-GO)

**Escopo:** somente arquivo de teste e PostgreSQL 18 descartável no GitHub Actions. Não é alteração de rotas reais, migration, ferramenta de exploração de contas reais, integração de produção nem aprovação para ativar operações financeiras.

## Por que o M40710 existe

M40700 adicionou assinatura HMAC com domínio, versão, digest SHA-256 da sessão, tenant, nonce, validade e escopo; somente um papel autenticador restrito consegue chamar a função emissora. O novo controle limita a emissão de ticket usando somente o digest. Entretanto, a chave HMAC está armazenada dentro de uma tabela protegida no próprio PostgreSQL sintético. Uma assinatura válida transmitida como parâmetro SQL também pode ser capturada antes da primeira utilização. A prova de uso único protege contra **repetição depois do consumo**, mas não identifica quem apresentou a assinatura primeiro.

## Provas adversariais M40710

1. O papel de autenticação sintético não consegue ler a tabela de segredo nem a de nonces e não executa o emissor antigo do M40680. O papel financeiro não usa o esquema assinador nem sua função.
2. Só digest SHA-256, papel SQL autenticador e variáveis GUC falsificadas não bastam sem a assinatura válida.
3. **Assinatura íntegra capturada antes do uso:** uma conexão que possui o papel autenticador consegue resgatar uma requisição assinada que não criou; o pedido legítimo posterior falha como replay. O primeiro resgate obtém um ticket e consegue consumir o dado da sessão sintética, demonstrando **ausência de prova de posse**. A simulação não lê nem captura tráfego real.
4. **Corrida:** seis conexões independentes disputam a mesma assinatura, duas rodadas, e em cada rodada somente uma recebe ticket. Isso comprova uso único do nonce no contexto estudado, **não** que o vencedor seja o emissor legítimo.
5. **Chave extraível pelo proprietário do banco de testes:** o papel privilegiado proprietário do fixture lê a chave da tabela e consegue forjar uma assinatura válida para outra sessão ativa e tenant autorizado. Isso demonstra que a ACL de leitura limita papéis de aplicação, mas não cria segredo não exportável frente ao comprometimento da administração do banco.
6. Assinaturas e tickets ainda atravessam parâmetros SQL; os riscos de logging, observabilidade, memória, reuso antes do consumo e comprometimento da credencial do SQL autenticador permanecem abertos.

## Limitações e requisitos para qualquer integração real

A demonstração usa dados, usuários, segredos e transações fictícios no CI, sem rede externa e sem simulação de interceptação de produção. Não comprova comprometimento existente, ausência de vazamentos ou falha nas sessões reais. Não cobre concorrência de revogação com consultas já abertas, múltiplos nós, janelas de indisponibilidade, separação física do emissor, injeção fora das funções testadas, outras funções SQL legadas nem escrita financeira.

Uma arquitetura candidata precisará avaliar uma **fronteira independente de assinatura** com gestão e rotação apropriadas de chaves (KMS/HSM/Vault ou outro serviço adequado), protocolos de prova de posse ou vínculo criptográfico ao cliente/canal, proteção de logs, menor privilégio e auditoria independente. A utilização de HMAC com chave acessível ao DBA sintético e uma prova transportável não corrige esses riscos.

**NÃO adaptar as funções sintéticas para o banco original sem auditoria e autorização expressas.** A vulnerabilidade GUC spoof nas rotas reais não foi remediada. FastAPI no aparelho permanece sem identidade do processo atestada.

## Guardas e marcadores

- M40710_LOW_PRIVILEGE_SIGNING_SECRET_AND_ISSUER_ACL=PASS
- M40710_DIGEST_PLUS_AUTH_ROLE_WITHOUT_SIGNER_KEY=DENIED
- M40710_PREUSE_CAPTURED_SIGNED_CLAIM_ACCEPTED=CONFIRMED_NO_GO
- M40710_CONCURRENT_SIGNED_CLAIM_SINGLE_REDEEM=PASS
- M40710_DATABASE_OWNER_HMAC_KEY_EXTRACTION=CONFIRMED_NO_GO
- M40710_EXTRACTED_HMAC_KEY_CAN_FORGE_SESSION_CLAIM=CONFIRMED_NO_GO
- M40710_SIGNED_CLAIM_SQL_PARAMETER_EXPOSURE=NOT_REMEDIATED
- M40710_ORIGINAL_GUC_SPOOF=NOT_REMEDIATED
- M40710_ORIGINAL_PG_5433=NOT_ACCESSED
- M40710_LOCAL_DB_WRITES=NONE; M40710_MIGRATIONS=NONE
- M40710_SERVICE_RESTARTS=NONE
- PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED

Qualquer sincronização no Termux deverá ser **source-only**, após a CI e com verificação de commit exato e hashes; nenhuma migração ou reboot autorizado.
