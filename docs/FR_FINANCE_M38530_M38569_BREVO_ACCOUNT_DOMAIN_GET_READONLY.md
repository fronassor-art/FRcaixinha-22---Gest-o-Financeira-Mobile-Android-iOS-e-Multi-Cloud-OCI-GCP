# FR Finance AI Studio — M38530–M38569 | Prova de status no painel da conta Brevo, GET somente leitura

**Checkpoint real anterior:** M38529, commit a63b756, 2.083 testes Python no Termux, Cloudflare consultou o domínio `frfinance.com.br`. Root SPF limitado, código Brevo, DMARC e seus relatórios observados, dois CNAME `brevo1` e `brevo2` detectados; `M38329_DNS_SHAPE_COMPLETE=TRUE`.

## Por que esta etapa é diferente dos testes DNS?

O DNS já está publicado em uma configuração compatível com a Brevo. Isso não comprova que **a conta do provedor** tenha reconhecido o domínio. A documentação oficial da API Brevo oferece o GET de um domínio:

- `GET https://api.brevo.com/v3/senders/domains/frfinance.com.br`
- Campos `verified` e `authenticated` indicam os estados observados na conta.
- Objeto `dns_records` pode conter `status` para `brevo_code`, `dkim_record` e `dmarc_record`. Sua ausência é exibida como `NOT_RETURNED`, sem presumir aprovação.
- **NÃO executar** `PUT /authenticate`: isso alteraria o estado de autenticação, fora do escopo deste pacote.

Documentação oficial:
https://developers.brevo.com/reference/get-domain-configuration
https://developers.brevo.com/docs/domain-authentication-and-verification

## Entregas

- M38530–M38539: avaliação pura, sem IO, para `verified`, `authenticated` e indicadores dos três registros na resposta JSON; valida nome exato de domínio e booleanos rigorosos; bloqueia resposta não correspondente. Nunca registra domínio de terceiros ou credenciais.
- M38540–M38549: CLI `backend/scripts/aistudio_brevo_domain_account_readonly.py` com modo `offline` e `live AUTHORIZE_BREVO_DOMAIN_STATUS_GET_ONLY`. Exige terminal interativo com `getpass` (entrada invisível) da **chave API do Brevo**, diferente da senha SMTP. Não recebe chave por argumento nem variável de ambiente, não grava no disco e não a imprime. Falha sem TTY, autorização ou chave válida.
- M38550–M38559: requisição HTTP GET de URL fixo, TLS com CA/hostname, sem redirecionamentos e sem proxy; resposta máxima 32KiB, application/json, detecção de chaves JSON duplicadas e erros convertidos em códigos fixos. Nunca imprime o JSON bruto, e-mails de criador, Brevo code, DKIM ou a chave de API.
- M38560–M38569: testes com clientes HTTP injetados e chaves fictícias, sem requisições reais; verifica recusas de domínio divergente, permissões, status não autenticado, duplicação de campos, MIME, tamanhos, falta de autorização, 401/403/404/429/500 e ausência de mutações, envio ou ativação.

## Uso no Termux

Modo offline, sem chave e sem rede:

```sh
python backend/scripts/aistudio_brevo_domain_account_readonly.py offline
```

Somente se o operador **já possuir uma chave API Brevo** com acesso a consulta de domínios, e decidir autorizar a leitura, executar no terminal interativo:

```sh
python backend/scripts/aistudio_brevo_domain_account_readonly.py live AUTHORIZE_BREVO_DOMAIN_STATUS_GET_ONLY
```

A chave é solicitada em um prompt oculto **no próprio Termux** (não digitar a chave no chat, nem em comandos shell persistidos no histórico). Se só houver login/senha SMTP, este comando não deve tentar reutilizá-los; utilizar o painel Brevo para verificar o status de domínio, ou criar posteriormente chave API exclusivamente por meio do painel com permissões apropriadas.

Alternativa **sem chave de API**: no painel Brevo, ir a *Configurações > Remetentes, domínios, IPs > Domínios*, localizar `frfinance.com.br` e observar o estado `Authenticated`. Não confundir `Branded` com autenticação do domínio.

## Garantias

Se a resposta de GET acusar `authenticated=true` e `verified=true`, isso comprova somente **o estado informado pela conta Brevo naquela consulta autenticada**, sem comprovar SMTP STARTTLS, assinatura e alinhamento DKIM em e-mail recebido, tratamento de bounce ou propriedade/consentimento de cada destinatário. Não aumenta automaticamente `LIVE_GATES` nem permite envio ou usuários reais.

Nenhuma migração SQL; banco PostgreSQL 5433 preservado; sem comando OCI, Gmail, SMTP ou Pix. `EMAIL_REAL=OFF`, `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCAO=BLOCKED`.
