# FR Finance M40430 — isolamento visual entre sessão, perfil e caixinha

O M40420 foi aprovado (7/7 jobs; parser e 50/50 testes) e sincronizado no Termux
em `9442f12`. Uma revisão do ciclo React apontou janela entre a renderização
de um **novo** perfil e o efeito que limpa o cache do perfil anterior.

M40430 associa os dados carregados à chave imutável de contexto da consulta
(`userId:tenantId:role`). Enquanto a chave do usuário atual não corresponder
à chave autenticada dos dados, o componente não apresenta lista, botões
administrativos, propostas nem respostas antigas. Mensagens de sucesso do
contexto anterior também não aparecem na nova caixinha. O diagnóstico de Push
não apresenta erro de sessão anterior após troca de login.

O backend continua sendo a única autoridade de permissões (RBAC/RLS).
M40430 complementa a segurança da interface; **não substitui** uma verificação
de montagem/desmontagem real no APK.

CI: suíte offline M40430, renderização SSR inicial dos perfis, nenhum fetch,
POST, conexão ao banco ou notificação. CI geral também fará Android debug
assinado se o fornecedor Maven Central estiver disponível.

`FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO`; `PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`;
`PRODUCTION=BLOCKED`; nenhuma migração ou reinício no celular.
