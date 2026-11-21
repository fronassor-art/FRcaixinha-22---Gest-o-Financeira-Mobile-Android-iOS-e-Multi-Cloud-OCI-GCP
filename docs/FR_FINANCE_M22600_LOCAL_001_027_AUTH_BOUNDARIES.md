# M22600 — auditoria local de autorização 001–027, sem reaplicação

A auditoria estrutural M19200 já confirmou 46 tabelas e migrações locais 028–044. M22600 fornece uma prova adicional dos controles de autenticação criados nas migrações 001–027, mas não tenta inventar ou reconstruir o histórico da execução de cada arquivo SQL.

Somente leitura, no Termux e banco exclusivo frcaixinha_aistudio_dev/5433:
- perfis frc_ai_app, frc_ai_auth, frc_ai_verifier não privilegiados e ligados apenas aos papéis técnicos corretos;
- aplicação/autoridade Auth sem SELECT de hash; verificador com leitura de hash e inserção de prova limitada, sem emissão de sessão;
- funções exclusivas da autoridade de emissão de sessão e de rate limit;
- RLS com FORCE em users, sessions, auth_login_proofs, auth_login_rate_limits;
- gatilhos de revogação da credencial e guardas de sessão/prova.

Uso após sincronizar, sem arquivos modificados:

    export AI_STUDIO_APPROVED_SHA="$(git rev-parse HEAD)"
    python3 backend/scripts/aistudio_auth_baseline_readonly.py

A senha será solicitada em modo oculto e não deve ser enviada ao chat. É uma operação de consulta. Se algum guardião falhar, a saída será BLOCKED; não reinstalar migrações e não mudar roles para forçar PASS.

As migrações 001–027 não possuem trilha imutável por arquivo comprovada neste auditor. Mesmo um PASS será estrutural/privilegial, não histórico e não homologação de produção. A validação remota com TLS, backup/restauração e três perfis é etapa posterior OCI, sem dinheiro real.
