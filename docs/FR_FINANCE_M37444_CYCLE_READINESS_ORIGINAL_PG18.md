# FR Finance M37444 — prontidão para abertura de ciclo, banco original

M37443 foi homologado localmente: registros R$100 zerados; 1 user, 1 tenant,
2 memberships, 79 sessions, 6 audit_events, 2 triggers ativos e ambas
restrições SQL de R$150 VALIDATED. Nenhum segundo banco foi criado.

Este pacote audita a prontidão do código de abertura para o administrador,
exclusivamente via SELECT, no mesmo PostgreSQL 18 `frcaixinha_aistudio_dev`
porta 5433. Confirma os objetos da migração local 044 já presentes:
`public.cycle_open_create` SECURITY DEFINER, função de autorização
admin, FORCE RLS, duas proteções append-only, grants limitados e
ausência de ciclos/contribuições experimentais.

A regra permanece: administrador define explicitamente valor por cota e
ciclo, mínimo R$150,00 (R$100 e R$149,99 não passam). Sem default R$150.
`FR_FINANCE_CYCLE_OPEN_ENABLED` deve permanecer OFF para esta auditoria.
O M37444 não cria ciclos, não autentica usuário real, não realiza Pix,
não aplica a migração 044 e não adiciona novos registros.

A auditoria estrutural M37370 foi atualizada para reconhecer restrições
M043 tanto antes quanto depois de validação. M37444 exige as duas
`convalidated=true`, comprovadas após M37442.

Após CI integral 6/6 PASS, sincronizar com o Termux e executar apenas:
`PYTHONPATH=backend python backend/scripts/aistudio_m37444_cycle_readiness_readonly.py`.
Se BLOCKED, NÃO usar scripts antigos de migração 044: alguns exigem banco
ainda com constraints NOT VALID e podem ser incompatíveis com o estado
atual. Homologação real de abertura exige fase específica e autorização.
