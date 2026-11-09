# FR Finance — M33400–M33800: pré-diagnóstico SaaS do cadastro de membros

**Checkpoint de origem:** M33300 `037568f100537eca03cd010e9857cf891a5ab6dd`.
Mesmo projeto AI Studio / repositório / branch / PR #2. Não envolver FRcaixinha 2.2.

## Integração que não existia antes

A rota `POST /invitations/preflight/saas-capacity` verifica, somente
sob sessão autenticada de **TENANT_ADMIN** e RLS do PostgreSQL:

1. Tenant ativo e publicação do contrato de adesão solicitada.
2. Entitlement e preparação da própria caixinha e responsável, vinculados
   ao pagamento registrado no banco e ao plano comercial.
3. Licença vigente, plano ativo e registro de pagamento conciliado no banco.
4. Membros ativos + uma vaga, cotas ativas e limites do plano.

O retorno é um **snapshot**, não um lock. Não consulta e-mail, CPF ou senhas.
Não aceita quantidades, atores, preços ou provas de pagamento do cliente.
Faz `SELECT` com contexto de tenant obtido exclusivamente da sessão.
Sempre responde `status=BLOCKED`, `activation_authorized=false`,
`final_capacity_reserved=false` e `writes_performed=false`.
Nenhum dado do Mercado Pago é verificado contra o provedor nessa etapa.

A candidata a migração local **045** cria apenas uma política de leitura:
o administrador vê limites do **plano para o qual sua caixinha já tem
entitlement visível por RLS**. Sem entitlement, não vê planos. Master mantém
suas regras anteriores e a camada de Auth não recebe grants adicionais.
Não existe autorização para executar o SQL no PostgreSQL local porta 5433.

## Homologação

- Unitários adversariais: cross-tenant, Master, Membro, licença inválida,
  pagamento não conciliado, plano cheio, contrato não publicado.
- Testes PostgreSQL 18 em CI com entitlements sintéticos e conta não
  privilegiada, assegurando isolamento dos planos de dois tenants.
- CI de API/frontend/Android preservada e inventário SQL com hash.
- Exibição positiva de **capacidade candidata** não atesta vaga reservada,
  nem receita, nem autorização de ativação.

## Pendências para produção

Banco real local 5433 **não recebe** a migração 045. Antes de aplicá-la
serão necessários autorização explícita, backup/restauração e auditoria
de identidade. A admissão final ainda exige transação atômica de convite,
vínculo, uso único, consentimento, cobrança SaaS autenticada no provedor,
reserva e compensação de capacidade; além da OCI/HTTPS e dos 27 gates
técnicos/externos. Valores sintéticos de testes NÃO validam Mercado Pago.
