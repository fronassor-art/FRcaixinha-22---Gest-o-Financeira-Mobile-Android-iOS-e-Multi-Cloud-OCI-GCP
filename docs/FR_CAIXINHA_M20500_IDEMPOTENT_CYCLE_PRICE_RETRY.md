# FR Caixinha AI Studio — M20500, reenvio seguro de alteração de cota

- Baseline M20400: migração 042 aplicada e verificada localmente em 05/11/2026, 45 tabelas, RLS PASS, backup AGE verificado; **essas evidências pertencem ao relatório do operador no Termux**, não à CI.
- M20500 não altera SQL nem executa novas migrações. A tela de contribuição passa a reter a mesma chave de idempotência quando a mesma solicitação precisa ser repetida após falha de rede.
- Uma mudança no usuário/papel/tenant (scope), ciclo, valor ou justificativa gera chave nova. Após uma resposta confirmada a chave é descartada; respostas de sessões antigas não podem sobrescrever o feedback.
- A chave é gerada no aplicativo com \`crypto.randomUUID()\` e enviada ao backend. Não se persistem tokens, QR Codes, dados financeiros ou chaves entre sessões.
- A proteção de backend M20400 continua a fonte autoritativa: auditoria append-only, validação do administrador pela sessão PostgreSQL e revisão pendente quando já existem cobranças. A UI não liquida nem reajusta obrigações existentes.
- **Limitação:** a chave só permanece na memória enquanto a tela/componente está montado; após reiniciar o aplicativo, a recuperação de solicitações deve ser feita por consulta autoritativa no banco, nunca presumindo sucesso.
- A CI testa o reuso da chave e seu isolamento; o APK e a API ainda exigem homologação funcional no Android com backend local disponível.
- Mercado Pago/OCI, Pix real, conciliação, rateio e pagamento de empréstimos **não são ativados** por este pacote.
