# FR Finance M40370 — senha original, duas caixinhas e plano de dados RLS

Data: 17/11/2026. Continuação direta do M40360 (121764f), na mesma branch da PR #2 Draft.

## Lacuna fechada, sem duplicar autenticação

O M40360 já provava 23 verificações de login pela rota original, senha e
funções PostgreSQL originais, sessão revogável e capacidade de Crédito
Especial com dinheiro real desligado. Entretanto, a resposta de
/special-credit/capabilities não consulta linhas patrimoniais.

M40370 **amplia o mesmo teste M40360** em
backend/tests/test_rls_isolation_ci.py, com as mesmas cinco
identidades e o mesmo banco descartável já configurado nas jobs PG16/PG18.
Não cria autenticação, rota, workflow, banco, tabelas nem migrações.

## Matriz adicional em PostgreSQL descartável

Para cada um dos cinco tokens de login por senha (Admin A, Admin B,
Membro A, Membro B e Master), a suíte exige:

- GET de cotas próprias sob RLS, com UUIDs positivos da fixture: Admin A
  enxerga 2; Admin B, 1; Membro A, 1; Membro B, 1; Master, 403.
- GET do dashboard original com source=POSTGRESQL_RLS, tenant,
  papel e contagem coerentes; Master, 403.
- GET da lista minimizada de membros apenas para cada administrador;
  membros e Master, 403, sem CPF, e-mail ou telefone na resposta.
- GET de cotas e dashboard da caixinha oposta, com cabeçalhos
  X-Role e X-Tenant-ID falsificados: HTTP 403.
- GET de cotas próprias com cabeçalhos falsos: não muda o perfil nem
  revela UUID extra; Master continua negado.
- Depois do logout, a mesma sessão não acessa mais as cotas: HTTP 401.

Uma chamada sem token também deve retornar 401. São 36 verificações
adicionais de rota (5 × 7 + 1), sem mudar o total 23 do M40360.
A fonte dos IDs são linhas sintéticas da fixture original, e não
uma consulta ao banco do telefone.

## Evidências e limites

A CI principal .github/workflows/validacao-atualizacao.yml
já executa a suíte inteira no PostgreSQL descartável da job original
e a seleção M40360/M40370 no PostgreSQL 18 da job existente. A saída
M40370_DATA_PLANE_CHECKS=PASS_36_OF_36 deve aparecer
**somente após** os 36 asserts e o resultado real da CI concluir.

Isto atesta leitura RLS de quotas e dashboard com token
original, não comprova leitura autenticada das seis tabelas
special_credit_* SQL110/111 no mesmo banco. A etapa
seguinte continua sendo planejar essa ligação na CI de maneira isolada,
sem reaplicar migrações no Termux.

Não comprova teste do APK físico, dados reais, pagamentos, provedor,
produção, criação da VM OCI ou estado local atual do FastAPI.

## Segurança operacional

A branch permanece atualizacao-ai-studio-9b46a63187, PR #2
em rascunho, main sem merge. No Termux não criar
diretórios, bancos ou repositórios adicionais; preservar o FR Finance
original e o PostgreSQL 18 frcaixinha_aistudio_dev em
127.0.0.1:5433. NÃO reaplicar SQL110/111, executar
initdb ou reiniciar FastAPI/PostgreSQL.

PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF;
PRODUCTION=BLOCKED; comunicações reais e disparos externos OFF.
