# FR Finance M40380: autenticação original e dados SQL110 (PostgreSQL descartável)

Checkpoint anterior: M40370, commit a2757da, 7/7 jobs CI aprovados.
M40340/M40350 usavam tokens pré-semeados e funções SQL sintéticas;
M40360/M40370 verificavam login original, mas não linhas SQL110.

M40380 acrescenta job ao workflow existente M40340, sem substituir os
testes anteriores. Inicializa um único banco PostgreSQL 18 descartável
frfinance_ci_credit em 127.0.0.1:5432 dentro do runner GitHub Actions,
executa o schema original de autenticação 001–027, depois SQL110+111
sob o modo CI_DISPOSABLE. Não cria banco no Termux.

Cinco identidades sintéticas autenticarão por POST /api/v1/auth/login e
funções PostgreSQL originais de emissão, prova, promoção e sessão.
A mesma sessão consultará as seis tabelas com FORCE RLS via
get_current_session/get_rls_db_connection, com 60 comparações entre
admin e membros A/B e Master. Também verifica impersonação HTTP e
revogação por logout, sem dinheiro ou mensagens reais.

A prova só poderá ser declarada PASS após a CI da nova job concluir;
publicar o teste não significa que a integração foi homologada.
Permanece PR #2 Draft; sem merge, deploy, migração no banco original,
reinício, envios externos, crédito real ou Pix.
Pendente: APK físico, integração homologada de provedor, conciliação,
OCI e requisitos operacionais de produção.
