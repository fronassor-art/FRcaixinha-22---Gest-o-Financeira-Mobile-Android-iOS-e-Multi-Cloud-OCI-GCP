# FR Finance — M37463 | leitura de contrato SaaS vinculada ao token de sessão (CI)

## Entrada homologada

M37462 (`329081c`): 61 testes PASS no Termux e 6/6 jobs do GitHub
Actions aprovados; PostgreSQL descartável confirmou hash SHA-256 do
bearer vinculado ao ID de sessão, renovação e revogação de token
sintético, com preservação das tabelas financeiras preexistentes.

## Objetivo executado

Comprovar que o identificador da sessão validada por
`get_current_session` e a posse do bearer sintético são
necessários **conjuntamente** para ler o mesmo documento
`PLATFORM_LICENSE`, request, desafio, preço e tenant em PostgreSQL
descartável.

### Novo leitor SQL somente leitura

`backend/app/saas_token_scoped_offer_readback_ci.py` contém a consulta
`TOKEN_SCOPE_SQL`, parametrizada por:
`(verified_session_id, admin_id, tenant_id, request_id,
 sha256_do_bearer_sintetico)`.

A consulta realiza JOIN direto com `public.sessions` — e
**não confia apenas** na tabela sintética
`saas_preprep_sessions_m37458_ci`. Exige mesmo ID, papel,
usuário, tenant, hash da sessão persistida, não revogação,
expiração futura, vínculo administrativo ativo, documento publicado,
challenge não expirado e preço versionado. O token bruto e seu
hash **não são retornados** pela consulta.

`build_token_scoped_ci_context` valida o resultado do PostgreSQL
e limita a vigência ao menor período entre o token renovado,
o registro atual da sessão e o contexto sintético. O servidor não
aceita papel, tenant, valor, token-hash ou documento atribuídos
pelo cliente como autoridade.

### Prova antes/depois da revogação

Em `backend/scripts/aistudio_staging_chain_ci.sh`, o script
`backend/scripts/aistudio_m37463_token_scoped_offer_ci.py` roda duas
vezes no `frcaixinha_staging` descartável:

1. **Antes da revogação:** chama a dependência real
   `get_current_session` contra o PostgreSQL de testes com
   bearer fictício, depois faz SELECT de contrato no mesmo banco.
   Demonstra correspondência entre token, sessão, administrador,
   tenant, request e desafio. Hash incorreto, sessão diferente,
   request de outra caixinha ou administrador diferente não
   retornam linhas.
2. **Depois da revogação M37462:** exige HTTP 401 para o token
   revogado e zero linha de contrato; outro token ativo do mesmo
   administrador não herda o desafio de sua sessão anterior.

A consulta administrativa usa conexão
`default_transaction_read_only=on` e somente o banco
`127.0.0.1:5432/frcaixinha_staging`. O script não executa
inserções de contrato, pagamento, ledger ou licença. Somente o
M37462 faz a revogação de sessão **sintética** nessa sequência.

### Regressões

`backend/tests/test_m37463_token_scoped_offer_readback_ci.py`
valida bloqueio de claim de sessão legado, papel Master/membro,
tenant cruzado, horários inválidos, documento/versão adulterados,
preços inválidos, digest malformado, e permissões ambientais de CI.
O preflight do GitHub Actions executa esses testes sem banco local.

## O que o PASS **não** comprova

- O login é uma sessão de **fixture CI**, não uma credencial
  fornecida ou validada por um administrador real.
- O contexto contratual M37458 continua sintético e a prova não
  equivale a aceite juridicamente verificável.
- O resultado do SELECT **não pode ser usado como autorização
  posterior de escrita**: uma revogação pode ocorrer depois da leitura.
  A implementação comercial precisará revalidar a sessão e o
  contrato **na mesma transação** que gravará o aceite, sob
  controle de acesso/RLS, locks e idempotência.
- A leitura usa conta administrativa **exclusivamente descartável**.
  Nenhuma credencial de produção, OCI, webhook Pix ou usuário real
  foi provisionado.

Em resumo: API de contratação real, licenças, pagamentos,
Pix, ativação e migrações no banco original permanecem **OFF**.

## Homologação segura no Termux

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37463_token_scoped_offer_readback_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Nunca executar no Termux** o runner
`aistudio_m37463_token_scoped_offer_ci.py` ou
`aistudio_staging_chain_ci.sh`.

## Próxima prioridade

M37464: provar a transação descartável de aceite sem janela
entre revalidação do token, leitura de oferta e a tentativa de
preparação; bloqueio de revogação concorrente e replay, mantendo
ativação real totalmente desabilitada.
