# FR Finance M39075 — preservar edição de campanhas ao alternar apps Android

## Causa confirmada no código
`src/App.tsx` executava `if (resumeValidationPending) return <main .../>`
sempre que o Android voltava de segundo plano e a API autenticava
novamente `/auth/me`. Esse retorno destruía a árvore React ativa,
reiniciando os formulários e seus estados locais ao mostrar o app outra vez.

## Correção implementada
1. A validação de sessão **continua obrigatória** ao retomar o Android,
   inclusive `visibilitychange` e `pageshow`. O app exibe bloqueio
   de tela em primeiro plano, mantém a árvore React montada, mas oculta e
   desabilitada via `aria-hidden` e `inert`. Sem confirmação da
   autenticação, ela permanece inacessível; falha/401 invalida sessão.
   Se a sessão permanecer válida, **mesma aba, scroll e campos** continuam.
2. `src/components/SaasPromotionsPanel.tsx` grava sincronicamente cada
   campo de rascunho: plano, periodicidade, preço promocional, título,
   benefício, vigência e justificativa. Não salva um rascunho no servidor
   até que o Master clique explicitamente `Criar rascunho`.
3. `src/services/masterCampaignDraftPersistence.ts` limita essa gravação
   ao Master autenticado e à identidade técnica do usuário, TTL 72h,
   validação de formato de entrada, limite de caracteres e fail-closed.
   Não guarda token, senha, sessão, membros, saldos, contratos, Pix ou
   resposta confidencial do banco. O armazenamento é privado da WebView
   instalada no Android, não sincronizado com OCI.
4. Se o Android encerrar a WebView completamente, o login será exigido
   novamente (tokens **somente em memória**). Após novo login Master
   válido, e existindo rascunho ainda não expirado, reabre aba LICENCAS
   e restaura os campos da promoção, inclusive retorno à seção.
5. `Descartar preenchimento local` remove rascunho não submetido;
   um rascunho gravado e confirmado pelo PostgreSQL também limpa esse
   cache local. Logout explícito limpa o cache do Master atual.
   Falha HTTP, rede indisponível ou mudança de app NÃO apagam o cache.

## Limitações honestas
- Não é possível impedir que Android encerre um aplicativo sob pressão
  de memória; a solução recupera a edição **após autenticação novamente**.
- Limpeza de dados do app, desinstalação ou armazenamento local bloqueado
  apagam/impedem o cache. O app informa quando não pode salvar.
- Dados promocionais não são criptografados em repouso pelo aplicativo,
  mas ficam na sandbox da WebView e são apagados no logout explícito
  ou após 72h (ao serem consultados); não é armazenamento de credenciais.
- Não altera outras telas de edição fora da manutenção da árvore de
  componentes ao voltar do segundo plano. Não afeta sessões expiradas,
  isolamento multi-tenant ou dados do PostgreSQL.

## Homologação de aparelho — M39075
1. Master > Licenças > Promoções SaaS. Digitar título, valor, benefício,
   datas e justificativa sem submeter. Conferir aviso de salvamento local.
2. Pressionar Home, abrir outro app e retornar via aplicativos recentes.
   Deverá aparecer brevemente `Verificando sua sessão`, e então
   a mesma tela deverá reaparecer, campos e scroll intactos.
3. Se o Android realmente matar o processo, entrar novamente como
   o **mesmo Master** e conferir a recuperação do preenchimento.
4. Tentar com outra identidade/role: dados de um Master não podem aparecer
   para outro usuário, administrador ou membro.
5. Acionar `Descartar preenchimento local`: apenas campos temporários
   limpam; PostgreSQL e campanhas registradas não são alterados.
6. Confirmar `M39059_STATUS=PASS_LOCAL_TEST_READINESS` (revalidação real),
   sem modificar PostgreSQL 5433, sem habilitar Pix ou e-mail.

Implementação: nenhuma migração SQL nova, nenhuma mudança no backend,
nenhuma senha redefinida, nenhum evento financeiro.
