# FR Finance M41180 — contenção de leituras HTTP com GUC legado

Data: 26/11/2026  
Base revisada antes do refinamento: 159eed876ae2431204f560017c9fbfb31bb32379  
Situação: contenção source-only; NO-GO de produção preservado.

## Escopo

A dependência compartilhada get_rls_db_connection agora recusa GET e HEAD com HTTP 503 após validar o formato da sessão e antes de consultar o pool financeiro. As rotas que ainda dependem do contexto GUC legado deixam de obter dados por essa dependência.

A mudança é centralizada. Ela não modifica as rotas POST nem comprova que suas consultas e autorizações estejam prontas para operação financeira real. O teste POST usa somente um pool e uma conexão falsos em memória.

A autenticação da requisição pode consultar seu armazenamento de sessões antes de executar esta dependência. Portanto, a evidência de M41180 é estrita: zero chamadas ao pool financeiro legado para GET/HEAD. Ela não afirma ausência de qualquer consulta de autenticação na aplicação real.

As seis rotas de leitura do ledger protegidas pelo M41150 continuam usando sua dependência própria. Na ausência do provider, M41170 já as fecha com HTTP 503 antes do pool.

A exceção de leitura GET exige uma marca definida dentro da instância FastAPI em memória por um harness CI existente e pré-validado. Além de M40070, M40080, M40340, M40380, M40400 e M40410, o fixture compartilhado de M40360/M40370 agora recebe a marca somente após verificar `current_database()`, porta 5432 e versão PostgreSQL 16–19 no banco descartável `frcaixinha_ci`. O fixture usa `monkeypatch` para remover a marca ao fim de cada teste. Os workflows declaram `CI_M40360_DISPOSABLE=1` junto de `PGOPTIONS=-c frfinance.m40360_ci=DISPOSABLE_ONLY`. O teste E2E de onboarding por três papéis também marca sua instância somente após a mesma verificação da identidade do PostgreSQL descartável; esse harness permanece em `development`, sem atestar homologação real. O guard ainda exige correspondência entre o identificador CI e o GUC, flags reais OFF, configuração de desenvolvimento e todos os DSNs no loopback com nomes de banco contendo o componente `ci`. M40070/M40080 usa `frcaixinha_ci`; M40340/M40380/M40400/M40410 reutiliza `frfinance_ci_credit`. Essas exceções mantêm provas positivas existentes de autenticação, RLS, revogação e ciclo de campanha somente nos processos CI marcados. O guard também rejeita `homologation`; nenhuma exceção habilita leituras no Termux ou em produção.

## Evidência automatizada

O teste M41180 executa a aplicação FastAPI em ASGI com sessão sintética que passa pela validação estrutural do M40610 e sem override do guard de sessão:

- 24 requisições concorrentes GET/HEAD recebem HTTP 503.
- O pool financeiro legado é chamado zero vezes para essas requisições.
- Um POST de controle ainda percorre a dependência existente usando conexão falsa, sem driver, DSN ou banco real.
- O workflow geral executa o mesmo arquivo de teste; o workflow M41180 roda a verificação dedicada.

A sessão do teste é sintética. A execução comprova o comportamento do código nessa fixture e não é atestação independente de identidade, runtime, processo ou banco.

## Limites e pendências

M41180 não corrige a falsificação de GUC SQL documentada no M40570; não substitui a custódia independente do emissor e das credenciais do M40730; não altera os gates M40840/M40930; e não libera produção. O bloqueio de GET/HEAD pode deixar telas dependentes das rotas legadas indisponíveis até que recebam um contexto SQL aprovado.

Não houve alteração de SQL, migrações, conexão ao PostgreSQL autoritativo, gravação, reinício de serviço, reload de runtime, operação externa ou promoção dos requisitos da matriz. Permanecem 330 IDs e 2.310 etapas; a evidência independente e o aceite continuam pendentes.

## Estado operacional

- SQL delta: nenhum.
- Banco original: não acessado.
- Conexões reais e gravações: nenhuma.
- Migrações e reinícios: nenhum.
- Runtime: não recarregado nem atestado.
- PIX_REAL, PAGAMENTOS_REAIS e ATIVACAO_REAL: OFF.
- PRODUCTION: BLOCKED.
- Estado do gate: NO-GO.
