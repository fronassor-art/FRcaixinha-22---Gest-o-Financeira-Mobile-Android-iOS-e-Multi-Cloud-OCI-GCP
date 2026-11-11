# FR Finance M37987–M38000 — Atraso cadastral separado de competências

Origem M37986, commit cc3f394: 620 testes offline no Termux.

O Caderno Mestre distingue 90 dias civis de atraso de três competências mensais consecutivas vencidas. Essas hipóteses não são equivalentes. Este pacote acrescenta os dois sinais independentes na API de leitura RLS, na validação de resposta do cliente e no painel de membros, sem transformar histórico não conciliado em bloqueio automático.

Implementações: módulo Python puro de análise de sinais, três campos obrigatórios no contrato do endpoint GET member-risk, validação TypeScript dos limites e coerência de cada campo, painel de revisão e testes adversariais de 0–130 dias, 1–89 dias com três competências, dados inválidos e cross-tenant. Mudanças de servidor e cliente precisam ser implantadas em conjunto.

Testes novos: backend/tests/test_m37987_registered_risk_signals_ci.py e suite backend/tests/test_member_cycle_risk_api_ci.py; frontend src/tests/member_cycle_risk_ci.test.ts. Nenhuma transação financeira ou migração nova; banco e OCI não tocados.

Critérios GO/NO-GO de produção continuam: 20 requisitos técnicos, sete externos e 50 AT pendentes. Esta API não prova origem bancária, não decide elegibilidade, não bloqueia usuário, não confisca principal e não autoriza fechamento ou Pix. REAL_PIX=OFF. PRODUCTION=BLOCKED.
