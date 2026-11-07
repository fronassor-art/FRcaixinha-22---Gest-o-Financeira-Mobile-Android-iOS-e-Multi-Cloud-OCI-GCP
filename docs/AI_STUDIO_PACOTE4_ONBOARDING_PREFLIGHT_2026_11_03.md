# FRcaixinha AI Studio Mobile — Pacote 4
## Pré-análise de convite administrativo e arquitetura (sem execução real)

Baseline de desenvolvimento:
9c79f279882bc8778779b59f752864d440465c56, branch
atualizacao-ai-studio-9b46a63187, PR #2 Draft.

## Funcionalidades deste pacote
- Nova aba exclusiva Master: "Preparação de acesso".
- GET /api/v1/master/admin-onboarding/capabilities: informa todas as etapas
  ainda bloqueadas. Não fornece credenciais, identidades ou dados financeiros.
- POST /api/v1/master/admin-onboarding/preflight: pré-análise de um UUID
  de caixinha com SELECT sob RLS; opcional UUID hipotético do candidato
  (não consulta users). Resposta obrigatoriamente bloqueada.
- Distingue tenant ativo/suspenso, candidato ausente, autoaprovação
  proibida, e requisitos ainda não aprovados.
- Justificativa é validada apenas no request e não é persistida nem
  reproduzida na resposta. Interface não persiste dados em localStorage.
- Simulador puro de transições e testes adversariais de ator, expiração,
  estado, identidade, independentemente de servidor ou banco real.
- Frontend fail-closed e testes CI GitHub Actions (backend e TypeScript).

## Modelo planejado de eventos (não implantado)
REQUESTED -> EMAIL_VERIFIED -> MASTER_REVIEW -> APPROVED ->
INVITE_PREPARED -> DELIVERED -> ACCEPTED -> ACTIVE.
Saídas terminais: REJECTED, REVOKED, EXPIRED.
Cada transição real deverá exigir assinatura de sessão, idempotency-key,
consulta de registro atual com SELECT ... FOR UPDATE, validação da prova
de titularidade, verificação de contrato válido, dupla aprovação
independente, auditoria atômica, verificação de status de tenant e usuário,
token aleatório armazenado apenas como hash com validade curta,
negação de reutilização e de autorizações cruzadas.

## Requisitos que ainda BLOQUEIAM ações reais
- MFA forte do Master, validação de dupla aprovação, provas de titularidade,
  emissão de token de uso único e revogação segura, provedores de entrega,
  verificação transacional de identidade/vínculo, trilhas auditáveis e
  autorização jurídica.
- Não usar endpoint legado de convite para emissão real; atualmente
  retorna HTTP 503 por desenho.
- As migrations 014/018 fornecem estruturas preparatórias mas a política
  atual mantém GRANT/SELECT/INSERT bloqueados para o papel da API.
  Não executar migrations reais nem contornar regras RLS.
- Nada deste pacote cria usuário, membro, token, convite, aprovação,
  pagamentos, operações financeiras ou alteração de status.

## Checkpoint e homologação
Sincronizar Termux somente após todos jobs PASS; reiniciar o FastAPI
apenas quando for testar novas rotas (checkpoint de APK a cada dez builds,
ou antes se alteração crítica exigir). Manter assinatura persistente,
app ID, PostgreSQL local segregado e PR Draft até aprovação explícita.
