# FR Finance — M39085 | Ciclo vigente e inventário SQL de leitura (13/11/2026)

## Evidências recebidas do Termux
- M39084 sincronizada até `1c77eeb2b71aec8ff6df0531cdd6667ef73dd876`.
- Dependência `@capacitor/push-notifications@8.1.2` restaurada em `node_modules` com integridade SHA-512 do lockfile: PASS.
- Typecheck complementar TypeScript 6 no Android ARM64: PASS; TypeScript 7 permanece o compilador oficial na CI Linux.
- Testes de sessão, notificações, ciclo-readiness (M39083), navegação de campanhas (M39076) e contrato Push (M39020): PASS.
- Git limpo; sem migrações, escrita financeira ou ativação de canais externos.

## Problema revelado pelo GitHub Actions
No commit M39084, workflow `FR Finance M39010 - Credito Especial e Canais (CI offline)`, execução `43537494756`, job `132269928707`, falhou com três testes da M39046. Resultado do job: **118 testes PASS, 3 FAIL**. A origem é o inventário congelado em 17 consultas `SELECT` antes da rota M39083 `GET /cycle-readiness`, que adicionou a 18ª consulta somente de leitura.

## Correção M39085
- Rebaseline de `EXPECTED_QUERIES=17` para `18` em `backend/scripts/frfinance_m39046_execute_selects_readonly.py`, preservando **2** consultas com `FOR SHARE/FOR UPDATE` que nunca são executadas em transação somente leitura.
- Com 18 consultas totais, 16 consultas seguras são executadas para dois contextos de sessão sintéticos (`TENANT_ADMIN` e `TENANT_MEMBER`): expectativa atualizada para **32** SELECTs sob RLS.
- Teste específico garante que a nova consulta escalar de ciclo utiliza tenant, `ABERTO`, datas de início/fim e reconhece resultado `EXISTS`.
- Teste adversarial garante que `EXISTS` verdadeiro para identificadores fictícios é rejeitado como vazamento, sem mascarar o erro.
- Novo workflow `frfinance-m39085-credit-readonly-inventory-ci.yml` para testes 39045/39046/39083/39082/39081, sem conexão ao PostgreSQL real.

## Limites e aceitação
Ajustar contagem de consultas **não é prova de que a consulta real foi executada no PostgreSQL original**. GitHub Actions utiliza simulação e não recebe credenciais. Qualquer inspeção posterior do banco original exigirá conexão supervisada, papel correto, transação READ ONLY e identificadores sintéticos sem criar registros. Nenhuma migração SQL será reaplicada; o PostgreSQL FR Caixinha 2.2 permanece intocado.

A PR #2 deve permanecer draft, sem merge, Pix, comunicações externas ou ativação de crédito real. A homologação de CI M39085 exige workflow aprovado; a homologação local exige testes de regressão executados no Termux.
