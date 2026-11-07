# M22300 — Anti-CSRF de escritas por cookie no backend FastAPI

Requisições HTTP com cookie frcaixinha_session são enviadas automaticamente pelo navegador; CORS não substitui defesa de CSRF. A política de M22300 exige exatamente um Origin presente na lista já autorizada de CORS antes de processar POST, PUT, PATCH, DELETE ou outros métodos não seguros.

Origem ausente, duplicada, estranha ou fora da allowlist resulta HTTP 403 e cabeçalhos no-store. Leituras seguras GET/HEAD/OPTIONS não são alteradas. O aplicativo Android, que usa Bearer em memória sem cookie, segue pelas mesmas regras de autorização existentes.

Quando a OCI tiver domínio final, APP_URL deverá ser a origem HTTPS verdadeira; nenhum domínio local será permitido na produção. Esta mudança não fornece autenticação, não concede novas permissões de tenant e não ativa dinheiro real.

Testes em CI verificam a função pura e o FastAPI, incluindo rejeição antes da rota e preservação das respostas 503 do serviço não configurado.
