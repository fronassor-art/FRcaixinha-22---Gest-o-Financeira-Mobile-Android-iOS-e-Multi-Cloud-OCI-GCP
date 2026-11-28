# FR Finance M41280 — verificação do desafio e destino fixado no assinador descartável (NO-GO)

Base M41270 3ee13fc775d880d561ae481b332ad38111b6c19f; retorno operador M40600/M40941 PASS_SOURCE_ONLY_NO_GO, HEAD idêntico à branch/PR #2. CP26-0061/CTM-07, CP26-0062/CTM-08, CP26-0257/TENANT_RLS, TEC-09, TEC-12; matriz 330/2310 preservada.

O worker Linux recebe chave sintética do desafio SQL uma única vez no bootstrap autenticado por credenciais de processo; não em ambiente/argv. Verifica HMAC do desafio em domínio FRF-M41260 antes de assinar FRF-M41270. Fixa por digest do ticket o primeiro destino criptograficamente válido; repetição exatamente igual é idempotente, outro destino/tenant é negado mesmo com desafio SQL autêntico. Capacidade 4096, sem evicção nem reatribuição; saturação falha fechada. Negativa autenticada não destrói o canal; falha de transporte continua indisponível. SQL mantém consumo único e verificação própria.

Testes: desafio inválido não fixa ticket, HMAC canônico, concorrência de dois destinos válidos, isolamento de tenant, capacidade esgotada sem evicção, repetição idempotente, chave de bootstrap sintética, duas transações reais PG18 descartável e regressão das seis rotas. Negativas anteriores do SQL ainda usam provas sintéticas da fixture owner para testar o binder independentemente da negativa do worker.

Limites: primeiro destino válido ainda é escolhido pelo processo pai autorizado; bootstrap de teste e chaves simétricas acessíveis ao owner/fixture, pin volátil por processo e sem durabilidade/revogação independente. Não comprova custódia real, exclusividade global entre workers, proteção contra comprometimento do pai/owner nem substituição de GUC/ACL real. Não habilita provider real, não altera SQL110–113, não altera regras financeiras ou matriz de aceite. Próximo passo: protocolo de autorização inicial emitido por identidade independente antes da assinatura e prova de ciclo de vida/restart em staging autorizado.

M40840=NO_GO; M40930=HTTP503; MIGRATIONS=NONE; ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
