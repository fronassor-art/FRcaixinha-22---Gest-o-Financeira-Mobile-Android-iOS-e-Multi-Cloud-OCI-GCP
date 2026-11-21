# Pacote 10 — Inventário de sessões / FRcaixinha AI Studio Mobile

Baseline: d55a6dd7d75401715936924dbf8309eceb0428bd.
Branch atualizacao-ai-studio-9b46a63187. PR #2 Draft.

- Parser estrito do GET /api/v1/auth/sessions: fonte autoritativa
  POSTGRESQL_AUTH, UUID, timestamps, duplicidade, perfil, tenant e
  exatamente uma sessão atual compatível com o papel autenticado.
- Rejeição de registros com campos sensíveis (hashes, credenciais,
  token, IP, e-mail, CPF ou saldo) e reconstrução minimizada.
- Resposta de sessão antiga após logout e novo login é descartada.
- Revogação de sessão alheia confirmada provoca uma nova consulta
  ao inventário PostgreSQL, não apenas remoção da linha no cliente.
- UI ignora erros de requisições antigas para evitar confusão
  entre sessões e perfis.
- Testes TypeScript com resposta 401, indisponibilidade 503,
  revogação, contexto trocado, malformação e duplicações.

A API é a autoridade de autenticação e revogação. Este controle de
frontend nunca concede permissões. Nenhuma migration ou consulta em
conta/banco real. Sem convite real ou transação financeira, sem merge.
A vistoria manual seguinte será APK 180, salvo risco crítico.
