# FR Finance M40400 — privacidade de membros da mesma caixinha

Complementa M40380 e M40390, apos homologacao fisica do APK M40390 (8/8 PASS).

O M40380 ja comprovou 60 leituras entre duas caixinhas. O M40390 comprovou
20 negativas HTTP com sandbox OFF. O M40400 testa a lacuna restante:
DOIS MEMBROS DISTINTOS da MESMA caixinha A, com campanhas, grants,
destinatarios e preferencias distintos, usando credenciais autenticadas reais
do codigo FastAPI original e as seis policies SQL110 FORCE RLS originais.

Rodar exclusivamente no job GitHub Actions M40380 com PostgreSQL18 descartavel,
database frfinance_ci_credit, port 5432, apos M40380 e M40390.
O script exige todos os gates de M40380 antes de importar bibliotecas DB.
Sao 72 assercoes de leitura (6 identidades, 2 tenants e 6 tabelas),
verificando IDs por membro e separacao de Master, admins, tenants e
outbox/auditoria. Nada e enviado; outbox sempre BLOCKED_EXTERNAL.

Nao rodar no Termux, Debian, banco FR Finance 5433 nem banco FR 2.2.
Nao autoriza sandbox local, migrações, reinicios ou ativacao real.
PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED.
PR #2 continua Draft.