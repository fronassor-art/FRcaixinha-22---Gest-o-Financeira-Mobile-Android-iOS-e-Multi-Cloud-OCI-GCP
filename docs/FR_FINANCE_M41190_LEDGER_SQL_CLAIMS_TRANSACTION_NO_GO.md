# FR Finance M41190 — validação SQL de claims e encerramento transacional do ledger

Base M41180: 29ae306f2fd15a03a6198033b02347382c27f8f4. CP26-0061 / CTM-07, CP26-0062 / CTM-08, CP26-0257 / TENANT_RLS; TEC-09 e TEC-12. Os 330 IDs e 2.310 etapas permanecem intactos. Issue #5 aberta. PENDING_INDEPENDENT_EVIDENCE.

## Correção de código

A capability opaca de 64 hexadecimais não comprova por si identidade, papel, tenant ou escopo. Nas seis rotas de leitura do ledger, depois de instalar o contexto transacional, o gateway consulta a função já existente no protótipo descartável m41050.current_claims() na mesma conexão e transação READ ONLY. Exige exatamente uma linha que corresponda ao usuário, papel, tenant e READ_ENTRIES esperados da sessão HTTP; ausência, duplicidade ou divergência recebe 401, falha de consulta ou resultado malformado recebe 503. Revalida expiração da sessão após o provedor e após a leitura. Não usa GUC legado como fallback.

O gerenciador de contexto assíncrono propaga a exceção do consumidor à transação, encerrando-a antes da devolução ao pool. Falha ou cancelamento durante RESET ALL / DISCARD TEMP invalida a conexão; cancelamento não é convertido em resposta de sucesso.

## Ensaios exigidos

Suíte offline: match positivo; usuário, papel, tenant e escopo divergentes; claims ausentes/duplicadas/malformadas; erro SQL; rollback por exceção e cancelamento do consumidor; descarte por falha ou cancelamento no reset. Suíte PG18 existente: seis GET positivos, rejeição de capability válida de outro membro/tenant e de capability desconhecida, empréstimo dos dois slots do pool sem contexto residual e recuperação positiva, além das regressões existentes. A CI geral executa os testes offline; workflow M41150 executa os testes com PG18 descartável. Resultados aguardam execução no SHA publicado.

## Limites

A função SQL pertence ao fixture existente, não ao catálogo autoritativo. Nenhum SQL/migração/role é criado ou aplicado no banco original. A comparação não distingue sessões diferentes da mesma identidade/papel/tenant porque a função protótipo não retorna ID de sessão; também não prova que a política RLS autoritativa usa essas claims, nem que o emissor é independente. A aplicação padrão continua sem provider e responde 503; M41180 permanece, assim como M40570, M40730, M40840 e M40930. Não habilitar staging ou runtime com este pacote. A integração da função canônica no catálogo revisado, vínculo de sessão, custódia e evidência independente são próximos passos; não confundir contenção com correção completa.

ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE; DB_WRITES=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
