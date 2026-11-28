# FR Finance AI Studio — super macropacote M34900–M35300

**Origem:** M34800 `ea6bd5668a6e9acdf9a4d0c7550b0f0eb1e53c92`.
**Projeto:** exclusivamente AI Studio, mesma branch/PR #2.

## Avanço real na trilha do backend do provedor

Em vez de criar outro sistema de cobranças, o pacote reforça o adaptador
**existente** `fetch_authoritative_saas_payment`:

1. Consulta autenticada via `GET https://api.mercadopago.com/v1/payments/{id}`.
   O token e o ID da conta recebedora são exclusivamente da plataforma
   FR Finance; não confundir com tokens OAuth de caixinhas.
2. Resposta HTTP 200 com limite de tamanho, JSON com campos únicos
   (inclusive objetos internos), rejeição a constantes não numéricas e
   `Decimal` em vez de float para os valores.
3. `SaaSPlatformPaymentRecord` representa valores do pagamento armazenado
   em banco protegido; nunca deve nascer de payload de webhook ou app.
4. A consulta somente retorna *candidato de conferência*: status aprovado,
   mesmo identificador, mesma conta recebedora, referência, moeda BRL,
   modo live/teste e valor em centavos. Reembolso total ou parcial bloqueia.
5. Nenhuma chamada pública usa o novo serviço; flags de governança
   continuam desligadas por padrão. Em testes, todos os GETs são
   `httpx.MockTransport` e **não houve conexão nem credencial real**.
6. Nenhum `INSERT`, `UPDATE`, criação de entitlement, membro, receita
   ou ledger. Nenhuma autorização para Pix ou produção.

**Nota de segurança:** a tag `SERVER_SIDE_SAAS_PAYMENT_INTENT` não
autentica origem; é uma restrição de contrato de interface. A futura
integração com worker real precisará de leitura direta do registro
PostgreSQL com RLS/role adequado, cofre OCI Vault, confirmação de
credencial e titular da conta, trilha imutável, lock de tenant,
conciliador de três fontes e revalidação no momento do commit.

## Provas externas ainda pendentes

As provas operacionais seguem em zero até que se obtenha acesso
OCI funcional e HTTPS/DNS públicos, Vault/IAM, confirmação comercial do
Mercado Pago para este uso, verificação real do provedor por GET e
reconciliação completa; não promover CI sandbox a autorização de
operação real. A migração 046 está só versionada e continua **não
aplicada** no PostgreSQL local 5433. Catálogo permanece em 105 SQL,
pois este pacote altera Python e testes, não o esquema.

**Fonte da operação GET:** documentação do Mercado Pago Developers,
referência `GET /v1/payments/{id}`, autorização Bearer.
