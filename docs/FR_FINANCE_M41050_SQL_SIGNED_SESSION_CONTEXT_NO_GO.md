# FR Finance M41050 — contexto RLS vinculado a ticket (protótipo NO-GO)

Data-base: M41040, SHA 72a9a7f654da. Laboratório exclusivo PostgreSQL 18 descartável e testes offline. O pacote aproveita a emissão assinada de M40700 e o consumo de uso único de M40680; não cria segunda chave HMAC, segundo emissor SQL ou role privilegiada. Não altera rotas reais, migrations, runtime, banco original ou flags.

## Mapeamento de requisitos

CP26-0019 exige sessão verificada e segregação de papéis e tenants. CP26-0003 e CP26-0004 preservam Master fora dos dados privados e restringem Admin/Membro aos próprios tenants. CP26-0061 e CP26-0062 exigem sessão com papel explícito e validação RLS. Os IDs e sete etapas por requisito na matriz 330/2.310 ficam intactos; este pacote é prova técnica isolada, não aceite nem gate de produção.

## Lacuna coberta no laboratório

M40570 comprovou que um papel SQL de aplicação consegue definir app.current_role e app.current_user_id. M41050 acrescenta ao fixture M40700 um passo posterior: o papel financeiro consome o ticket já assinado, consulta o ticket/sessão verificados e cria um capability aleatório de curta duração. O PostgreSQL guarda somente o hash do capability, o digest da sessão, tenant e expiração. O capability é instalado por set_config transacional; o RLS ignora os GUCs antigos e resolve identidade pelo registro que só foi criado após consumo do ticket.

O teste cobre login app sem capability com GUCs Master falsos, capability de membro acompanhado por GUCs que alegam Master/outro tenant, Admin restrito ao tenant próprio, leitura de membro limitada ao próprio registro, cruzamento de tenants, tentativa Master, replay do mesmo ticket, consumo concorrente por seis conexões e revogação da sessão após emissão. Não há rota FastAPI conectada ao protótipo.

## Limites mantidos como NO-GO

- M40710 já provou que o owner/superuser do PostgreSQL pode extrair o HMAC secret de M40700 e forjar claims. M41050 reutiliza exatamente essa autoridade de laboratório; não a corrige.
- M40710 também provou que uma assinatura válida capturada antes do primeiro consumo pode ganhar a corrida. O capability de M41050 não repara esse risco de origem/canal.
- SQL arbitrário dentro da conexão autenticada pode ler o GUC app.session_capability e reutilizá-lo até expirar. A claim continua limitada ao papel, tenant e escopo que foram validados no ticket; vazamento da sessão e comprometimento do processo permanecem riscos.
- M40700 aceita apenas sessões TENANT_ADMIN e TENANT_MEMBER. Uma sessão MASTER não recebe ticket neste experimento e continua negada; fluxos administrativos Master permanecem bloqueados.
- A função e a política RLS são apenas dados e DDL sintéticos de CI. O PostgreSQL original continua usando o código e políticas históricos; nenhuma migration foi proposta ou aplicada.
- A saída atesta somente comportamento em uma instância descartável. Não prova credenciais, runtime, rotação/segredo independente, tráfego TLS, Android, OCI staging ou revisão independente.

M41050 pode orientar uma futura integração após corrigir a custódia de chave, origem de ticket, escopos e sessões reais. Hoje não remove M40840 NO-GO, M40930 HTTP 503 nem fecha issue #5.

MIGRATIONS=NONE; banco local, escritas e conexões = NONE; reload/restart = NONE. PIX_REAL, PAGAMENTOS_REAIS, ATIVACAO_REAL e comunicações reais = OFF. PRODUCTION=BLOCKED.
