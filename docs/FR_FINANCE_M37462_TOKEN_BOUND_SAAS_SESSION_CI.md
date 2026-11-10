# FR Finance M37462 — vínculo do bearer token ao ID de sessão PostgreSQL (CI)

## Checkpoint de entrada

M37461: commit `59c5265`, 77 testes aprovados no Termux e GitHub
Actions 6/6 PASS. PostgreSQL local da porta 5433 preservado. Pix,
licenças, pagamentos e ativação real desligados.

## Implementação

O M37462 corrige a lacuna de identidade técnica entre o
`get_current_session` autenticado e a fronteira HTTP experimental SaaS:

- `backend/app/dependencies.py` agora seleciona
  `s.id AS verified_session_id` **da mesma linha de sessão identificada
  por `s.token_hash=$1`**, valida revogação, papel/tenant,
  `auth_active_memberships(raw_token)` e renovação
  `auth_refresh_session(raw_token)` na transação PostgreSQL.
- O objeto `AuthenticatedSession` inclui campos opcionais
  `verified_session_id`, `verified_session_at`,
  `verified_session_expires_at` e `verification_source`.
  Os seis argumentos antigos continuam compatíveis. Objetos legados
  sem esses campos **não autorizam** o aceite SaaS.
- `backend/app/routers/saas_authenticated_contract_ci.py`
  compara o ID da sessão validada com o ID da leitura separada do servidor;
  exige fonte `POSTGRES_TOKEN_HASH_REFRESH`, timestamps válidos,
  janela máxima de cinco minutos, prazo do token posterior ao pedido e
  compatibilidade com a expiração do contexto. Cabeçalhos de papel
  enviados pelo cliente não alteram essas verificações.
- As regressões M37460 e M37461 foram adaptadas para refletir os
  campos de identidade esperados. Permissões reais seguem `false`.

## Ensaio PostgreSQL descartável (não é migração operacional)

`backend/tests/sql/m37462_disposable_bearer_session_ci.sql`
cria, somente no PostgreSQL `frcaixinha_staging` da CI, um
login técnico `frcaixinha_auth_token_ci` com privilégios herdados
exclusivamente do papel `frcaixinha_auth_role` e quatro sessões
fictícias, armazenando **apenas hash SHA-256 dos tokens**, nunca
bearers em texto claro no banco:

1. Sessão do administrador A vinculada ao contexto de teste M37458.
2. Outro token do administrador A com ID de sessão diferente.
3. Token de administrador e caixinha B.
4. Sessão A expirada para testar negação.

`backend/scripts/aistudio_m37462_verified_token_session_ci.py`
executa o verdadeiro `get_current_session` do backend contra o
PostgreSQL descartável usando a conta técnica sem superusuário.
Exige autenticação TESTE, valida correlação entre hash, ID, identidade,
papel e tenant, bloqueia token expirado/desconhecido, troca de sessão
e usuário de outra caixinha. Revoga o primeiro token por
`auth_revoke_session(text)`, exige HTTP 401 ao reutilizá-lo,
mas mantém a segunda sessão ativa.

Essas sessões são **inteiramente sintéticas**, criadas sem senha
verificada por pessoa real; o ensaio testa a verificação do token
de posse e as permissões PostgreSQL, não um login verdadeiro de usuário.

A conexão administrativa que lê o contexto usa
`default_transaction_read_only=on`. As únicas operações de escrita
são inclusão das sessões de teste e revogação no banco **descartável**.
Nada disso modifica o banco do Termux.

A execução está anexada ao fim de
`backend/scripts/aistudio_staging_chain_ci.sh`, após todas as outras
provas, com guarda de banco errado e de papel administrativo. A CI
`.github/workflows/validacao-atualizacao.yml` incorpora a nova
suíte Python e regressões M37460/M37461/legadas.

## Limitações e pendências

- O contrato publicado/preço e o desafio continuam fixtures sintéticos.
  Nenhum aceite jurídico foi atestado; nada permite emitir licenças,
  cobrar assinaturas, ativar membros ou executar Pix.
- O teste de token persistido não substitui um login real desde
  verificação independente de senha, MFA, desafio de consentimento,
  controle CSRF e verificação de revogação por requisição.
- A ativação comercial exige infraestrutura OCI, TLS/HTTPS, contrato
  revisado, PSP e webhook homologados, operação e monitoramento.

## Comando local seguro

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37462_verified_session_binding_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não executar no Termux** o SQL
`m37462_disposable_bearer_session_ci.sql`, o runner
`aistudio_m37462_verified_token_session_ci.py`
ou `aistudio_staging_chain_ci.sh`. Não alterar as flags reais.
