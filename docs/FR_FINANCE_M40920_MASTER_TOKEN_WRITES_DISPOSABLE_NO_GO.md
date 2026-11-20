# FR Finance M40920 — escrita Master SaaS por sessão independente (somente CI)

**Checkpoint de origem:** M40912 / \`04c90e9\` confirmado sincronizado pelo operador no Termux, sem DDL, sem alterações de ACL e sem reinícios. PR #2 segue Draft.

## Problema atendido

O fence M40900, devidamente limitado ao PostgreSQL 18 descartável, nega as permissões SQL113 antigas. O M40912 provou leitura das ofertas de novos administradores por sessão sintética de token verificado; **não** substituiu as operações de criação, publicação e cancelamento de campanhas pelo Master. Aplicar a revogação no banco original agora interromperia as rotas existentes.

## Protótipo M40920 — não implantar

A CI PostgreSQL 18 **descartável** repete M40900 e monta um broker \`NOLOGIN\` isolado, com função \`SECURITY DEFINER\` explicitamente exposta ao papel app apenas para a operação autorizada. Identidade Master vem de um **digest SHA-256 de token sintético em tabela protegida**, papel \`MASTER\`, autorização sintética independente, sessão vigente e sem revogação; jamais de \`app.current_*\`. O papel app perde leitura/escrita direta de SQL113 e não pode assumir a role broker nem gravar sessões/auditoria.

O ensaio inclui: criação append-only de rascunho, validação de plano/preço vigente, publicação sob revisão esperada, prevenção de concorrência e sobreposição pelo trigger SQL113, cancelamento append-only, auditoria atômica e rollback quando a auditoria é forçada a falhar. Contempla tentativas adversariais por membro, falso Master, token expirado/revogado/inválido, falsificação de GUC e dupla transição.

## Limitações e NO-GO

- A lista sintética de Masters e a emissão sintética de token não constituem um emissor real confiável. Um **token Master válido roubado** ainda consegue publicar e cancelar campanhas enquanto ativo.
- A role \`NOLOGIN\` é uma defesa parcial, não protege contra superuser, owner/issuer SQL comprometido nem contra vazamento de credenciais; M40730 continua **NO-GO**.
- O M40570 continua **NO-GO** porque os demais caminhos legados dependem de GUC. A listagem Master e as rotas HTTP reais **não** foram migradas para o novo broker.
- Não há revisão de custódia e assinatura fora do banco, proteção anti-replay, escopo de dispositivo, rate limit, telemetria independente ou ensaio de carga/concor­rência real. O resultado de CI não prova segurança do banco original.
- O PostgreSQL 18 do Termux e seus privilégios originais não são tocados. O protótipo apenas executa DDL e DML no contêiner de banco descartável GitHub Actions; **nenhum script de migração ou DDL para produção é publicado**.

**Próximos bloqueios:** substituir listagem Master e leitura tenant com autorização confiável, planejar origem/assinatura de sessão fora de SQL comprometido, inventariar ACLs e dependências do PostgreSQL original em somente leitura, testar rollback e restaurabilidade com aprovação expressa, auditar FastAPI e homologar Android fisicamente. Sem isso: PRODUCTION=BLOCKED.

\`MIGRATIONS=NONE\`; \`ORIGINAL_ACL_CHANGES=NONE\`; \`ORIGINAL_DB_CONNECTIONS=NONE\`; \`LOCAL_DB_WRITES=NONE\`; \`SERVICE_RESTARTS=NONE\`; \`PIX_REAL=OFF\`; \`PAGAMENTOS_REAIS=OFF\`; \`ATIVACAO_REAL=OFF\`; \`PRODUCTION=BLOCKED\`.
