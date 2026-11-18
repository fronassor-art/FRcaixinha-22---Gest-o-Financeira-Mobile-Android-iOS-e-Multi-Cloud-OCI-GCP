# FR Finance M40440 — isolamento entre duas sessões da mesma conta

Após M40430, o identificador visual incluía membro, caixinha e perfil, mas não
distinguia dois logins separados da mesma identidade.

M40440 adiciona a geração da sessão emitida por authService à chave de contexto
e bloqueia dados antigos antes de o efeito React limpar o cache. A falta
de token impede a exibição. Uma nova sessão exige buscar novamente os dados.
O token jamais entra na chave React nem é enviado a testes ou logs.

As ações de resposta, campanha e diagnóstico push exigem sessão atual.
Backend RBAC e SQL110 RLS seguem sendo a autoridade de permissões.

CI: 25 verificações puras, incluindo SSR inicial Master; nenhuma rede,
PostgreSQL, migrations, reinícios ou mensagens externas no celular.
Teste físico de troca rápida de contas permanece necessário antes de produção.

FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO; PIX_REAL=OFF;
PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.