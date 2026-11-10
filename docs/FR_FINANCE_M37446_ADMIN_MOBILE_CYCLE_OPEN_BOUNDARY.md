# FR Finance M37446 — Admin UI, API, sessão e prévia sem estado obsoleto

Checkpoint anterior: M37445 Termux 25 testes PASS e readiness original READ_ONLY_PASS.
A abertura de R$150, R$200 e R$325 foi ensaiada somente no PostgreSQL 18
descartável do GitHub (M37445) e revertida com ROLLBACK. Nenhum ciclo
foi aberto no banco local.

M37446 reforça a proteção do fluxo React/FastAPI:
- Somente TENANT_ADMIN pode chamar preview/opening no cliente; perfis
  MASTER/MEMBER e tenant não correspondente falham antes da rede.
  O servidor PostgreSQL continua o controlador final de autorização.
- Ano, valor, justificativa e caixinha alterados invalidam a prévia.
  Resposta de prévia que chega depois da edição ou mudança de sessão
  nunca autoriza abertura.
- O botão de confirmação verifica o conjunto de dados da prévia,
  o vínculo da sessão e o contexto antes de enviar a confirmação.
- Formulário fica bloqueado enquanto a confirmação está pendente;
  requisição de abertura não recebe retry automático em 503.
- A chave idempotente continua estável em tentativas iguais e vinculada
  ao contexto de sessão; resultados tardios não confirmam outro perfil.
- O valor mínimo permanece R$150 por cota/ciclo, explicitamente escolhido,
  não preço default, e sem emissão automática de dívidas.

Testes novos: Node/TS com fetch sintético, login fictício, fluxo de
prévia/recibo, troca de sessão, perfil MEMBER, 503, valores 150/200/325;
Python FastAPI com conexão falsa e assert no DML zero. **Não utiliza
PostgreSQL local, não cria usuários, não abre ciclos e não ativa Pix.**

Próximo passo: CI 6/6 PASS, sincronizar Termux, rodar os testes e
readiness M37444 read-only. A homologação visual no APK físico e o
endpoint autenticado real continuarão sendo etapas distintas.
