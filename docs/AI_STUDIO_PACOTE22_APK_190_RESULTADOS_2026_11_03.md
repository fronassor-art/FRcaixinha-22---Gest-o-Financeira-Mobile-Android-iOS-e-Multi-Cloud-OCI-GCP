# Pacote 22 — Checkpoint APK 190: resultados anuais por perfil

Base: b022d2ac810d535775ca890d0759c3cd12b770c8.
No aplicativo, FECHAMENTO do TENANT_ADMIN usa prévia agregada cadastrada
no PostgreSQL; MEU_RESULTADO do TENANT_MEMBER continua individual.
Ambas as leituras são segregadas por tenant e RLS, sem lançamento, Pix,
fechamento, lucro, rateio ou movimentação bancária. A nova rota do Admin
é somente GET e recusa MASTER/TENANT_MEMBER. O servidor continua como
fonte dos valores, não um cálculo local presumido.

### Checklist de homologação manual do APK 190
1. Atualizar o APK sem apagar dados ou alterar assinatura/appId.
2. Login Master e mudança explícita de perfil (sem acesso patrimonial).
3. Login Admin: FECHAMENTO mostra 12 contribuições de teste, R$ 1200
   devidos, R$ 0 pagos registrados e R$ 1200 pendentes.
4. Login Membro: MEU_RESULTADO mostra apenas os 12 registros do próprio
   Membro com os mesmos totais, sem resultados administrativos.
5. Verificar relógio e ícones Android fora do cabeçalho (safe area).
6. Verificar simulação Price R$ 500 em 5 parcelas, taxa 20% a.m. e
   resultado total R$ 835,96, sem contratar empréstimos.
7. Verificar logout, retorno de segundo plano e falha de API fechada.

NÃO afirmar lucros, saldo liquidado ou operação financeira. Sem mudanças
de parâmetros do Mercado Pago, contrato mestre, migrations ou PR/main.
