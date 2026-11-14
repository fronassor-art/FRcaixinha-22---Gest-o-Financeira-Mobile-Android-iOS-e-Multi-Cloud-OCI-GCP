# FR Finance AI Studio — Supermacropacote M31400–M31800

**Escopo:** controles SaaS 3.3, 3.4, 3.7–3.10 e regras de segregação.
**Situação:** implementação de engenharia e regressão CI, não homologação
operacional ou liberação jurídica.

## Implementações

- **M31400 — Capacidade transacional:** o PostgreSQL descartável recebe
  tabelas próprias de orçamento de vagas por plano e eventos imutáveis de
  reserva/liberação de MEMBRO/COTA. O plano ESSENCIAL da matriz histórica
  (20 membros, 40 cotas) é usado somente em fixtures artificiais.
- **M31500 — Serialização e isolamento:** `SELECT FOR UPDATE` na linha
  do tenant, papéis segregados, IDs de requisição únicos, defesa contra
  replay divergente, consumo de vagas já reservadas e escopo do administrador.
- **M31600 — Liberação rastreável:** evento de liberação append-only
  referencia a reserva exata, com bloqueio de dupla liberação e
  conservação da contagem de vagas; um papel de API não escreve na
  tabela de eventos.
- **M31700 — Ciclo de assinatura:** motor puro `saas_change_policy.py`
  avalia renovação, mudança de plano, cancelamento no fim da vigência,
  análise de reembolso e revisão de reativação. Os retornos indicam
  **somente candidato a revisão** e nunca efetuam cobrança nem
  alteração de entitlement.
- **M31800 — Evidência adversarial:** testes parametrizados Python,
  teste de corrida real em PostgreSQL CI com duas sessões competindo
  pela última vaga, check de catálogo, isolamento e trilha imutável.

## Limites de escopo

Os eventos de capacidade NÃO criam membro/cota real nem cobram Pix.
O esquema opera apenas no banco descartável `frcaixinha_staging`
e é bloqueado para o PostgreSQL do Termux (`5433`) e OCI.
As rotas de criação real de membros/cotas ainda precisam integrar as
verificações de quota com atomicidade no mesmo transaction boundary;
não basta um preflight separado do commit real.

Renovação efetiva requer nova fatura/conciliador e idempotência por
período. Cancelamento e reembolso exigem contratos aprovados,
rastreabilidade da identidade e prova do provedor; a simulação não
cria restituição nem altera o vencimento de licença já paga.

**Resultado não significa concluir as cláusulas históricas.**
Continuam pendentes provas externas do Master, OCI, Mercado Pago,
aceites jurídicos, testes de aparelhos e operação real.

## Termux

Pasta canônica: `$HOME/fr-finance`. Após GitHub Actions inteiramente
verde, sincronizar por fast-forward, executar o arquivo de testes Python
e a auditoria `aistudio_migration_inventory.py repo-check`.

**PROIBIDO** aplicar `backend/staging_migrations/060_saas_capacity_staging_only.sql`
e `backend/ci_migrations/059_saas_capacity_fixture_ci_only.sql`
à porta `5433`; são exclusivamente de CI. Não há migração local
autorizada neste pacote.
