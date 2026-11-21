# AI Studio — pacote de acesso único e integridade de sessão

**Escopo:** PR #2, branch `atualizacao-ai-studio-9b46a63187`.
Checkpoint anterior confirmado no Termux: `1cced19`.
**Não há migração adicional neste pacote:** esquema continua 001–018.
O PostgreSQL do AI Studio no Termux (18.6, porta 5433,
`frcaixinha_aistudio_dev`) permanece sem migrações e com zero tabelas
na última verificação fornecida pelo usuário.

## Entregas concretas

1. **Acesso único de membros e administradores:** o componente de seleção
   já existente no `App.tsx` foi aprimorado, sem duplicar login, painel
   Master ou identidades. Em vez de exibir apenas os códigos de papéis,
   mostra `Administrador Master — Plataforma`, `Administrador — Caixinha
   XXXXXXXX` ou `Membro — Caixinha XXXXXXXX`. A abreviação identifica o
   vínculo sem expor o UUID completo na interface. O backend continua
   sendo a autoridade sobre qual caixinha realmente pertence ao usuário.
2. **Contrato entre frontend e FastAPI:** `parseServerContexts` recusa
   papéis desconhecidos, tenant_id ausente, identificadores inválidos,
   MASTER indevidamente vinculado a tenant e vínculos duplicados.
   `switchContext` recusa uma segunda troca simultânea e verifica
   que o ID, papel e tenant retornados correspondem à sessão original
   e à solicitação; contexto incompatível encerra a sessão local.
3. **Corridas de rede:** chamadas antigas a `/me` ou `/contexts`
   não podem ressuscitar sessão encerrada ou substituir um contexto novo.
   A validade local do token não é prorrogada artificialmente por um
   `GET /me` sem expiração explícita. O logout limpa imediatamente
   o estado em memória antes de solicitar revogação ao backend. Uma
   resposta de logout atrasada não apaga um login novo.
4. **Troca atômica de perfil no backend:** `POST /api/v1/auth/switch-context`
   obtém bloqueio da sessão no PostgreSQL, confirma titularidade do token,
   status ACTIVE da pessoa, expiração/revogação e autorização ATUAL do
   vínculo. Somente então muda papel e tenant na mesma transação.
   A função é de homologação porque a própria autenticação ainda está
   bloqueada para produção. Master só recebe contexto Master quando a
   identidade tem direito à função; usar perfil membro exige vínculo
   real explícito e não permite consultar saldos com perfil Master.
5. **Recuperação de acesso:** a chamada do frontend foi corrigida para
   `/api/v1/auth/forgot-password`, que ainda retorna HTTP 503 explicando
   a indisponibilidade. Nenhum e-mail de redefinição é enviado ou
   confirmado artificialmente.
6. **Proteção de respostas:** middleware FastAPI acrescenta
   `Referrer-Policy: no-referrer` globalmente, `Cache-Control: no-store`
   e `Pragma: no-cache` a APIs sensíveis. Isto reduz cópias em caches,
   mas não substitui TLS ou ausência de tokens em logs/proxies.

## Testes

- `src/tests/auth_context_security.test.ts`:
  lista multitenant/multipapel, dados inválidos, troca, expiração,
  recuperação, requisição `/me` em curso durante logout, contextos
  atrasados e novo login com resposta de logout antiga.
- `backend/tests/test_rls_isolation_ci.py`:
  com PostgreSQL descartável, revogação do vínculo após alternar,
  sessão inválida não troca para outro tenant, Master alterna
  explicitamente para membro e volta para Master sem ganhar direitos
  financeiros como Master, headers de privacidade.
- `backend/tests/test_auth_context_security_headers.py`:
  respostas de autenticação não são cacheáveis, ausência de sessão
  impede acesso a endpoints protegidos, nenhuma falsa ativação.
- GitHub Actions: API offline, frontend + TypeScript, PostgreSQL 16
  descartável, PostgreSQL 18 em transação única e compilação APK
  debug. **PASS só deve ser declarado após a conclusão da execução.**

## Limitações e próximos bloqueios

- Não há inscrição pública de membros/administradores: convites e
  consentimentos reais ainda requerem provedor SMTP homologado,
  prova de titularidade, termos legais aceitos e autorização para
  migração/ativação. Não cadastrar pessoas reais.
- Não há cobrança SaaS real autorizada: Mercado Pago exige
  credenciais segregadas, reconciliação auditável, validação jurídica
  e liberação expressa. Nenhum Pix ou licença real deve ser emitido
  por esta rodada.
- A lista de caixinhas mostra um identificador abreviado, não nome
  personalizado, porque a função de autenticação autorizada retorna
  apenas `tenant_id` e `role`. A oferta de nomes exigirá contrato
  específico de permissões e testes adicionais.
- O código em GitHub pode ser sincronizado para o Termux **somente
  como arquivos**. Não executar `apply`, provisionar conta Master,
  instalar APK, enviar convite ou realizar transação financeira.
