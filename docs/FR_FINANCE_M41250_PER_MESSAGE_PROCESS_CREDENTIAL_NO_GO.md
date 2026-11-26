# FR Finance M41250 — credenciais de processo por mensagem (NO-GO)

Base M41240 7ad70727391ba31a74b5a050fd42f7032b8e1aa2; retorno real M40600/M40941 PASS_SOURCE_ONLY_NO_GO. CP26-0061/CTM-07, CP26-0062/CTM-08, CP26-0257/TENANT_RLS, TEC-09 e TEC-12. 330 IDs e 2.310 etapas preservados; Issue #5 PENDING_INDEPENDENT_EVIDENCE.

O assinador descartável M41240 substitui pipes por socketpair AF_UNIX SOCK_SEQPACKET privado, sem bind/listen ou serviço persistente. SO_PASSCRED é habilitado antes de enviar mensagens. Cada mensagem é validada com SCM_CREDENTIALS (PID, UID, GID do kernel); o filho exige o pai original, o pai exige o PID do filho. Frames limitados, truncamento/controle inesperado rejeitados, descritores recebidos fechados, timeout e falha fechada. Nenhum DSN ou bearer no filho. HMAC e chave separada M41240 continuam; nenhuma mudança de migração.

Ensaios: processo diferente do mesmo UID com descritor explicitamente herdado e payload válido recebe DENIED; pai autorizado continua assinando após negativas e frames malformados/longos; regressões da CI PG18 e seis rotas GET; perda do assinador HTTP 503. Resultado depende de execução CI do SHA.

Limites: credenciais por mensagem não são atestação do executável, não vinculam o PID Linux ao PID PostgreSQL, não resistem a pai autorizado comprometido, root, ptrace ou acesso à chave durante bootstrap. Não substituir M40929 nem considerar custódia independente real comprovada. Processo filho continua exclusivamente CI; nenhum provider padrão habilitado. M40570/M40730/M40840/M40930/M41180 vigentes. Próxima decisão depende de evidências independentes de staging, identidade do serviço, custódia e revisão da fronteira SQL.

ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; MIGRATIONS=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
