# FR Finance — M37461: leitura de sessão e oferta SaaS no PostgreSQL descartável

## Checkpoint anterior

M37460 homologado em Termux (`70d418e`, 39 testes) e GitHub Actions
(6/6 PASS). Banco local e 106 migrações SQL originais preservados.

## O que foi implementado

O M37461 retira **parte dos valores pré-montados em memória** do ensaio
SaaS, passando a consultar uma linha real do PostgreSQL **descartável
da CI**. A leitura usa os fixtures sintéticos M30900/M37458/M37459 e
faz JOIN parametrizado entre:

- sessão sintética de servidor (IDs, papel, validade e indicação de e-mail);
- tenant, administrador cadastral e vínculo `TENANT_ADMIN` ativo;
- desafio de aceite e request da cadeia sintética;
- versão do documento `PLATFORM_LICENSE` publicada, hash SHA-256;
- versão de preço, plano ativo e valor mensal/anual (10 vezes o mensal).

`backend/app/saas_server_context_readback_ci.py` faz o readback em uma
única consulta `SELECT` com os quatro identificadores parametrizados
`(session,tenant,admin,request)`, até dois resultados (duplicação
invalida). Após validar IDs, publicação, timestamps, preço, tenant e
papel, constrói um objeto `CITrustedServerContext` para os testes da
fronteira HTTP do M37460.

`backend/scripts/aistudio_m37461_server_context_readback_ci.py`
somente roda com GitHub Actions, `FRCAIXINHA_CI_ISOLATED=1`,
host `127.0.0.1`, porta 5432, banco `frcaixinha_staging`
e credenciais descartáveis `ci-test-only`. A conexão usa
`default_transaction_read_only=on` e verifica, na própria sessão
SQL, o banco, a porta, o papel e o modo `read_only`. Confere
que acesso Master, membro, administrador de outra caixinha ou request
incorreto não produz autorização, e que pagamentos, licenças e
lançamentos seguem zerados.

A regressão `backend/tests/test_m37461_saas_server_context_readback_ci.py`
testa valores adulterados, cross-tenant, preços inválidos, contratos
sem publicação, sessões vencidas e bloqueio do PostgreSQL do celular.

## Limitações de segurança explícitas

**A sessão do M37461 é um registro sintético, não um login comprovado.**
A dependência `get_current_session` do FastAPI verifica sessões reais
de homologação, mas o objeto `AuthenticatedSession` retornado ainda
não contém o identificador estável da sessão para comprovar, neste
pacote, que o bearer token validado corresponde à linha do fixture.
No runner, o `AuthenticatedSession` de teste é construído localmente
de forma declarada; não é autenticação E2E.

Portanto, mesmo com PASS:

- a rota M37460 continua com executor e readback bloqueados por padrão;
- não há prova de identidade real, assinatura contratual ou aceite
  juridicamente atestado;
- não são inseridos registros em `contract_acceptances`, não se
  cria cobrança, assinatura comercial, licença, ativação ou Pix;
- nenhum SQL do pacote é aplicado no PostgreSQL local porta 5433 ou OCI;
- o catálogo permanece com 106 SQL do repositório.

## Arquivos

1. `backend/app/saas_server_context_readback_ci.py`
2. `backend/scripts/aistudio_m37461_server_context_readback_ci.py`
3. `backend/tests/test_m37461_saas_server_context_readback_ci.py`
4. `backend/scripts/aistudio_staging_chain_ci.sh` — ensaio após M37459.
5. `.github/workflows/validacao-atualizacao.yml` — pytest isolado.

## Homologação local (sem executar PostgreSQL)

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37461_saas_server_context_readback_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não execute no Termux o runner
`aistudio_m37461_server_context_readback_ci.py` nem o
`aistudio_staging_chain_ci.sh`.**

## Próximo avanço planejado

M37462: vínculo confiável entre token de sessão verificado por
`get_current_session` e identificador de sessão/tenant retornado
pelo backend, com auditoria de expiração, revogação, rotação e
segregação de credenciais, inicialmente só em testes isolados.
Só após validação operacional + jurídica + PSP + OCI será possível
planejar a habilitação comercial.
