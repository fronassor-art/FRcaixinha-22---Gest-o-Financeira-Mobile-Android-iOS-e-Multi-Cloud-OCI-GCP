# Pacote 19 — Cotas e contribuições persistidas em homologação

Base: 919da3dcce8a01209cf5717b729aa2a98bc9fa7a
Branch: atualizacao-ai-studio-9b46a63187. PR #2 Draft.

A simulação Price foi comprovada em screenshot real do APK 180:
R$ 500,00 em cinco parcelas, 20% a.m., total R$ 835,96 e juros R$ 335,96.

## Avanços
- Novo teste integrado com banco PostgreSQL descartável, RLS real e
  rotas FastAPI verdadeiras de cotas e contribuições.
- Admin enxerga sua própria caixinha; membros somente a própria cota e
  contribuição; Master e outro tenant recebem recusa.
- Nenhuma chamada inicia Pix, altera capital ou concede crédito.
- Utilitário exclusivo para o banco AI Studio local: `--plan` somente
  leitura; `--apply` com confirmação explícita gera uma cota ATIVA e
  doze contribuições PENDENTES de 2027, vinculadas ao membership Membro
  do usuário inaugural (não à função Master).
- Valores de cota são lidos da política ACTIVE já cadastrada, não
  recriados a partir do contrato independente FRcaixinha 2.2.
- A execução é idempotente quando o conjunto esperado existe. Divergências
  impedem sobrescrita. Antes/depois confirma empréstimos, Pix e razão
  contábil sem alterações. Sem novos usuários, chaves ou credenciais.

## Aplicação restrita
O CI opera só em banco descartável frcaixinha_ci.
No Termux: testar `python3 -B backend/scripts/aistudio_homologation_contributions.py --plan`
e examinar o relatório. Aplicação só por confirmação no próprio terminal,
somente na caixinha inaugural, PostgreSQL 18 porta 5433.
Não reclassificar contribuições PENDENTES como QUITADAS: isso exige
conciliação efetiva com provedor ou um motor de testes explicitamente
separado, sem adulterar razão contábil.

O Mercado Pago seguirá a arquitetura endpoint/envelope e documentos mestres
já aprovados, sem substituição do modelo de integração.
