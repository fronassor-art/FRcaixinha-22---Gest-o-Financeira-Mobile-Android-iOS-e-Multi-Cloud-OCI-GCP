# FR Finance — prompt contratual M37434

O administrador ativo TENANT_ADMIN escolhe de modo explícito o valor por cota ao abrir cada ciclo. Mínimo contratual R$ 150,00 por membro/cota e ciclo. Não é valor fixo, não deve ser preenchido automaticamente. São válidos R$ 150, R$ 200, R$ 325 e valores superiores dentro do limite contratual. R$ 100 e R$ 149,99 são rejeitados por UI, API e regras SQL para novas operações.

Manter o mesmo aplicativo FR Finance AI Studio, repositório, branch atualizacao-ai-studio-9b46a63187, diretório Termux $HOME/fr-finance, PostgreSQL 18 porta 5433 e banco frcaixinha_aistudio_dev. Proibido criar outra base para resolver esse preço. Valor escolhido deve ser registrado por ciclo e tenant com sessão de admin, idempotência e auditoria. Nunca alterar lançamentos antigos silenciosamente, nem apresentar R$ 100 de testes como valor corrente de produção.

Fluxo: editar código e documentação primeiro no GitHub, aprovar todos os testes de CI, sincronizar somente fast-forward no Termux, executar diagnóstico do banco atual e propor migração transacional só após aprovação específica. Backup M37431, recuperação M37432 confirmados. M37433 de segunda base cancelado. Pix real e ativação real OFF.
