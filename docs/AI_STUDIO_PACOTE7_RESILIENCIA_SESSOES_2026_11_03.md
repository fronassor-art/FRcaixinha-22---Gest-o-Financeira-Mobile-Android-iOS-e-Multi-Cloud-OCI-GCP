# FRcaixinha AI Studio Mobile — Pacote 7: resiliência das sessões

## Baseline e autorização
- Baseline: e1c8c7ee70360612263b3ee1b2e73e6c4ca27d44
- Branch: atualizacao-ai-studio-9b46a63187 (PR #2 Draft)
- Sem migrations reais, sem acesso a contas/bancos do projeto independente,
  sem merge em main, sem troca da assinatura Android e sem movimentações reais.

## Implementado
1. Identificador efêmero de geração de sessão no AuthService: uma requisição
   captura token + geração atual e só processa o resultado se ambos coincidirem.
2. Respostas HTTP 200, 401, 403, 503 e erros de rede de uma sessão anterior são
   descartados após logout e novo login. Não podem expor dados antigos no novo
   perfil nem revogar a sessão nova.
3. HTTP 401 da sessão vigente encerra o token local, sem criar acesso offline.
4. HTTP 503 e falhas de rede não confirmam revogação: operação falha
   explicitamente, sem retry automático de transações financeiras.
5. /auth/me malformado invalida a sessão local (fail closed).
6. Resposta tardia de revogação de sessão não encerra login posterior.
7. Painel "Sessões da minha conta" permite atualizar a consulta após falha,
   evita exibir resposta de contexto anterior e esclarece a diferença entre
   bloqueio local e revogação remota confirmada.
8. Testes com mocks de rede no cliente, incluindo mutação financeira sem retry,
   e FastAPI com conexão falsa verificando expiração, revogação, ausência de
   vínculo, identidade Master inválida e indisponibilidade do banco.
9. CI inclui testes frontend, backend, PostgreSQL isolado e Android assinado.

## Limites de segurança
- A sessão não é salva em localStorage, cookies novos ou cache offline.
- O servidor PostgreSQL mantém a responsabilidade por expiração, revogação
  e autorização de usuários. Client guard é defesa adicional.
- Se o servidor estiver offline ao fazer logout, a sessão local é encerrada,
  mas o cliente NÃO garante revogação remota: confirmação depende do backend.
- Nenhum e-mail, convite, token, alteração de permissões ou migration real.
- Seguem bloqueados MFA Master e habilitação de convites em produção.

## Próximas fases
- Segurança das respostas e comportamento de rede no checkpoint Android 170.
- Revisar MFA forte e revogação de todas as sessões antes de uso produtivo.
