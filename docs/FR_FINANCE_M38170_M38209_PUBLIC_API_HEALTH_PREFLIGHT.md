# FR Finance AI Studio — M38170–M38209 | Diagnóstico de DNS/TLS + API FastAPI

Origem: checkpoint M38169, commit 1ddf2cf, 1.501 testes Python PASS no Termux. CI geral do checkpoint concluída com sucesso.

## Lacuna tratada
O M28200 verifica DNS e certificado TLS, porém não prova que o backend FastAPI responda. A nova checagem operacional foi implementada para ser executada somente após a criação real da VM, configuração do DNS e proxy HTTPS.

## M38170–M38209
- DNS público e IP fixado antes da conexão HTTPS, reutilizando a proteção M28200 contra IPs privados, link-local, interfaces internas, metadata OCI e DNS misto.
- TLS validado por CA pública e SNI, GET fixo em /api/health, sem tokens, cookies, login, querystring, redirects, ou gravações.
- Exigir HTTP 200, resposta JSON até 8 KiB, no-store, no-cache e nosniff. Identificar FR Finance / FastAPI e contrato sandbox-development. Um status falso de produção é recusado.
- Todos os endereços públicos resolvidos (máximo quatro) devem responder; alegações distintas sobre database_configured impedem o PASS.
- Novo comando explicitamente autorizado no intake do operador: probe-api-health APP_URL AUTHORIZE_PUBLIC_HEALTH_READ_ONLY. Apenas APP_URL previamente cadastrada; o operador não informa URL ou segredos no comando.
- Suite CI de casos adversariais com DNS, HTTP e JSON sintéticos, sem requisições de saída. Nenhum serviço real é declarado homologado pela própria CI.

## Operação futura, somente após existir backend público
Rodar manualmente no Termux (nunca rodar automaticamente antes de configurar a VM):

    python backend/scripts/aistudio_provider_intake.py probe-api-health APP_URL AUTHORIZE_PUBLIC_HEALTH_READ_ONLY

APP_URL deve apontar à origem HTTPS que de fato disponibiliza /api/health no proxy público; não necessariamente a um site estático. Se frontend e API forem hosts diferentes, antes será necessário adicionar uma origem API pública específica ao schema do intake, sem mudar APP_URL indevidamente.

## Limites
Um resultado real positivo comprova apenas que o hostname resolveu a IPs públicos, certificados TLS foram validados e um servidor remoto respondeu com o contrato /api/health. Não prova identidade da VM OCI, código/commit implantado, banco PostgreSQL, RLS, credenciais, login real, entrega de e-mail, contratos, Pix ou prontidão de produção. database_configured é uma alegação do servidor, NÃO consulta autenticada ao banco.

Sem migrations SQL, sem DB Termux 5433, sem mutações OCI, SMTP ou Mercado Pago. Até a execução operacional real, EXTERNAL_HEALTH=NOT_ATTESTED. EMAIL_REAL=OFF; PIX_REAL=OFF; ATIVACAO_REAL=OFF; PRODUCAO=BLOCKED.
