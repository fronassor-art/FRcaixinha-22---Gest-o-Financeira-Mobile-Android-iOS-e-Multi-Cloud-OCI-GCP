# FR Finance M41180 — contenção de leituras HTTP com GUC legado

Data: 26/11/2026  
Base de código: 4cc342b9fa610b24cc9bc392e2616b20862258b8  
Situação: contenção source-only; NO-GO de produção preservado.

## Escopo

A dependência compartilhada get_rls_db_connection agora recusa GET e HEAD com HTTP 503 após validar o formato da sessão e antes de consultar o pool financeiro. As rotas que ainda dependem do contexto GUC legado deixam de obter dados por essa dependência.

A mudança é centralizada. Ela não modifica as rotas POST nem comprova que suas consultas e autorizações estejam prontas para operação financeira real. O teste POST usa somente um pool e uma conexão falsos em memória.

A autenticação da requisição pode consultar seu armazenamento de sessões antes de executar esta dependência. Portanto, a evidência de M41180 é estrita: zero chamadas ao pool financeiro legado para GET/HEAD. Ela não afirma ausência de qualquer consulta de autenticação na aplicação real.

As seis rotas de leitura do ledger protegidas pelo M41150 continuam usando sua dependência própria. Na ausência do provider, M41170 já as fecha com HTTP 503 antes do pool.

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
