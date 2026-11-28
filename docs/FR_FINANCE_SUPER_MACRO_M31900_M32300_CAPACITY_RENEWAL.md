# FR Finance — M31900–M32300 (pre-homologação)

Base: M31800, c2f61f2e36144a49151ef54f4e6b696507054b2a. Branch canônica, PR #2.

- M31900: prévia tipada da criação de membro/cota (tenant, administrador, pagamento, licença).
- M32000: ocupação + reservas pendentes + novas vagas respeita o teto inclusivo; sem limite aprovado, negar.
- M32100: prévia de renovação exige preço positivo BRL, oferta, vigência, consentimento e limites.
- M32200: chave de termo estável (tenant/licença/vencimento/periodicidade), independente de request, preço e valor.
- M32300: revisão SQL persistida apenas em PostgreSQL descartável, UNIQUE por licença/período, row lock de tenant, histórico imutável e corrida adversarial.

O resultado nunca autoriza execução real, emissão de fatura, prorrogação de licença, geração de usuário, cotas ou Livro-Razão. O banco frcaixinha_staging contém somente fixture sintética antiga e nenhuma transação em provedor real. Preview Python NÃO substitui a checagem de capacidade no mesmo commit da inclusão real. O SQL não é uma migração de produção.

Não executar em PostgreSQL Termux 5433 nem OCI:
backend/staging_migrations/061_saas_renewal_review_staging_only.sql
backend/ci_migrations/060_saas_renewal_review_fixture_ci_only.sql

Pendências de produção: atomicidade com criação real, conciliação externa autenticada, aceites, segurança operacional, OCI, autorizações Master e homologação técnica das cláusulas. CI verde é apenas validação sintética.
