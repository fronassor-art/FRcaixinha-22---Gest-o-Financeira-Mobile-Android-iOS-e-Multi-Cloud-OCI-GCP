# FR Caixinha AI Studio — Auditoria do termo 'vendedor' / M3001–M3100

## Documentos examinados

No repositório AI Studio existem cópias históricas do `Contrato_Técnico_Mestre` e `Caderno_Mestre` cujo próprio nome é `FRcaixinha 2.2`. O contrato acessível da Biblioteca é `FRcaixinha_2_2_Contrato_Tecnico_Mestre_FINAL_APROVADO_2026-10-16.md`; o caderno de 17/10 é derivado desse contrato. **A frente AI Studio não é o repositório antigo** e esta nota NÃO altera o contrato, nem afirma a existência de um novo documento exclusivo AI Studio.

### Matriz de correspondência

| Norma histórica consultada | Sentido do requisito | Implementação AI Studio |
| --- | --- | --- |
| 2.1–2.3 | Apenas Master, Admin Contratante, Membro; identidade simultânea | `USER_ROLES` em `mp_provider_account_contract.py`, não adicionar SELLER |
| 7.1, 9.1 | Conta de licença Master separada da conta financeira de cada caixinha | `AccountPurpose.PLATFORM_LICENSE / TENANT_FINANCIAL` |
| 9.2–9.3 | Conexão MP autorizada por administrador, consentimento, cobrança correta | `provider_account_id` como identificador técnico da conta |
| 9.4–9.9 | Idempotência, prova externa, isolamento de ambientes e bloqueio de dinheiro em DEMO/HOMOLOGACAO | Toda revisão retorna `real_financial_operation_authorized=False` |
| 12.2-A, 13.1 | Referência `account_owner_ref`, `token_secret_ref`, segredo criptografado, mínimo privilégio | modelo de vínculo sem dados sensíveis; não ligar sozinho ao OAuth |
| 13.4–13.6 | Backup cifrado diário, WAL até 15 min (quando suportado), 35 dias, restauração trimestral, RPO 1h, RTO 8h | próximo pacote de requisitos OCI M3200 |

## Explicação técnica de 'seller_id'

A documentação oficial do Mercado Pago chama de *vendedor* o **titular da conta que autoriza uma aplicação via OAuth**. Suas APIs também utilizam `user_id` ou `seller_id` para identificar a conta beneficiária. Isso não cria um papel ou usuário de venda no FR Caixinha, nem define um mercado/loja dentro do software.

- **Vocabulário de produto:** `Administrador Contratante`, `Membro`, `Master`, `conta conectada da caixinha`, `conta da plataforma`.
- **Vocabulário técnico de integração:** `provider_account_id` no domínio e `user_id/seller_id` apenas na fronteira com Mercado Pago e esquema legado; não renomear campos exigidos pelo protocolo externo.
- **Escopo:** Administrador acessa apenas sua caixinha; Master acessa a conta de licença da plataforma e não seus saldos bancários; membros não recebem acesso às credenciais.
- **Sem poderes financeiros adicionais:** `allowed_to_query_provider=True` não equivale a permissão de Pix/fechamento. Uma prova de conta autorizada real exige vínculo persistente e sessão autenticada antes de chamar este revisor de domínio.

Fonte Mercado Pago: https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation

Não copiar código ou migrar banco do projeto independente FRcaixinha 2.2. Todos os commits deste pacote pertencem à PR #2 AI Studio, ainda Draft.
