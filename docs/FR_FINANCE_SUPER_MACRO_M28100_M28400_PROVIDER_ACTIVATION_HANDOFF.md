# FR Finance AI Studio — M28100–M28400: preparação operacional dos provedores

## Entrada / escopo exato

Checkpoint M28000 `97e875e`: **105 testes Termux PASS**, 92 SQL com
hashes verificados, `FR_FINANCE_PIX_REAL=DESATIVADO`.
`aistudio_provider_intake.py init` foi executado com sucesso,
mas o auditor detectou **0 de 13 campos públicos preenchidos**.

Esta é exclusivamente a frente AI Studio: branch
`atualizacao-ai-studio-9b46a63187`, PR #2 **DRAFT**, sem merge.
Não aplicar SQL CI/staging no banco Termux
`frcaixinha_aistudio_dev`, PostgreSQL 18 porta `5433`.

Objetivo: resolver as pendências reais de OCI, SMTP, identidade e
Mercado Pago **sem solicitar ou armazenar segredos no chat/GitHub**.

## M28100 — próximo campo pela dependência correta

O comando abaixo não faz rede ou escrita:

```bash
cd "$HOME/frcaixinha-aistudio-mobile"
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py next
```

Divisão em quatro etapas:

1. `01_ACCOUNTS`: descobrir região OCI escolhida e Application ID
   público da aplicação Mercado Pago (possível antes de VM).
2. `02_DOMAIN_AND_MAIL`: decidir domínio e verificar remetente SMTP;
   não inventar endereços nem usar conta pessoal sem permissão de envio.
3. `03_OCI_STAGING`: só depois de provisionar recursos sob orçamento,
   inserir OCIDs da instância, compartment, Vault e DNS do banco OCI.
4. `04_CALLBACKS`: configurar `redirect_uri` e webhooks HTTPS
   equivalentes aos cadastrados nos respectivos provedores.

Com campos já preenchidos, `next` omite esses itens e retorna
`NEXT_PUBLIC_FIELD` para o primeiro campo faltante.

**Exemplos (trocar pelos seus dados REAIS)**:

```bash
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py set OCI_REGION sa-saopaulo-1
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py set MP_APPLICATION_ID 1234567890123456
```

O primeiro exemplo de região só é correto se a sua tenancy realmente
tiver essa região. O Application ID acima é fictício. Jamais inferir
OCID de instância, Vault, domínio ou callback não provisionado.

## M28200 — DNS público e certificado TLS (opcional, consulta real)

Após inserir `APP_URL`, e **somente quando desejar um teste
de rede**, executar:

```bash
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py probe-https APP_URL AUTHORIZE_PUBLIC_TLS_ONLY
```

O script:
- lê um domínio público previamente aprovado pelo esquema;
- resolve endereços DNS; bloqueia TODOS os resultados privados,
  reservados, metadata, localhost e link-local;
- conecta por IP resolvido, na porta `443`, sem aceitar redirecionamento
  para endereços internos; TLS valida a cadeia de certificação e nome;
- não envia requisição HTTP, não obtém corpo, não usa cookie, não faz
  login, não acessa OCI/MP API e não envia SMTP;
- retorna apenas `M28200_PUBLIC_DNS_AND_TLS=PASS` se DNS e TLS
  estiverem válidos. A ausência do domínio ou falha de certificado
  permanece bloqueada.

Pode também verificar o hostname do `MP_OAUTH_REDIRECT_URI` ou
`MP_WEBHOOK_URL`, desde que o URL esteja preenchido previamente:

```bash
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py probe-https MP_WEBHOOK_URL AUTHORIZE_PUBLIC_TLS_ONLY
```

O teste de DNS/TLS não prova propriedade do domínio nem confirma que
o serviço de API atende corretamente. Não é prova de servidor OCI
implantado, login, webhook funcional ou Pix homologado.

## M28300 — inventário de nomes de segredos e IAM

```bash
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py secrets-plan
```

O comando apenas mostra **nomes de segredos exigidos**, local de
armazenamento previsto (OCI Vault), papel que necessita acesso e
segregação; nunca pergunta, lê, cria ou imprime senhas/token/chaves.

Os segredos principais terão propósitos distintos:
- SMTP password e webhook callback secret por serviços separados;
- Application Client Secret Mercado Pago, segredo `x-signature`,
  refresh token por vendedor e tenant, sem acesso pelo APK;
- AUTH_SECRET e HMAC de rate limit independentes;
- AES-GCM do envelope e HMAC indexador do destinatário por
  tenant, **nunca o mesmo segredo**;
- credenciais PostgreSQL diferentes para App, Auth e Verifier.

**Importante:** a mera criação de um Vault ou salvamento de
segredo NÃO ativa contas nem transações. É necessário provar a
política de IAM, a instância autorizada, a versão do segredo, o
isolamento RLS e as chamadas reais em staging.

## M28400 — checklist antes da passagem para produção

Regras de autorização e evidências que devem ter provas
independentes antes da liberação:

| Integração | Prova operacional |
|---|---|
| OCI | Conta/região ativa, VM criada, custo cotado, HTTPS, backup restaurado, RLS validado no banco remoto |
| SMTP | Domínio, SPF/DKIM/DMARC, TLS, segredo no Vault, teste em caixa própria e deduplicação/quarentena |
| Ativação | Posse do e-mail, MFA, aprovação independente, aceite explícito do próprio usuário, audit trail e rollback |
| MP Connect | Application ID, client secret no Vault, redirect registrado, consentimento do vendedor, PKCE/state e refresh |
| Pix de entrada | Pedido Orders autorizado pelo vendedor, idempotência, `x-signature` validada e conciliação |
| Pix de saída | Autorização comercial da modalidade e conta habilitada, limites, destinatário, antifraude, conciliação |

Verificações de sintaxe, build Android debug, CIDR/DNS/TLS ou testes
sintéticos não substituem os fatos anteriores.

### Custo / Oracle Cloud Free Tier

Antes de pagar um upgrade, verificar no Console OCI se a conta pode
usar recursos `Always Free eligible` e se a VM está disponível na
**home region**. O serviço Always Free inclui Ampere A1 com
1.500 OCPU-hours e 9.000 GB-hours por mês (equivalentes a até
2 OCPUs/12 GB em uma tenancy Always Free), sujeitos a limites e
capacidade. O trial prevê até US$300 em 30 dias se disponível.
**O Vault e outros serviços podem ter custos próprios**: verificar
sempre preço, cotas e avisos de orçamento antes de criar recursos
pagos; não habilitar Pay As You Go por suposição.

Fontes:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.oracle.com/cloud/free/
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm

### Mercado Pago — configuração e autorização

O Mercado Pago publica OAuth com authorization code, PKCE e
refresh; a configuração do redirect deve ser idêntica na aplicação
e na API. Para webhooks Orders e `mp-connect`, usar `x-signature`
HMAC com assinatura secreta guardada fora do Git/cliente.

Os pagamentos de saída **não** são consequência automática de
OAuth Connect. A API de Payouts possui endpoints específicos e
sua disponibilidade/forma de autorização precisa ser confirmada
comercialmente e documentada para a aplicação.

Fontes:
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/additional-content/security/oauth/creation
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications
- https://www.mercadopago.com.br/developers/pt/docs/payouts/resources/api-endpoints

## Comandos finais de coleta (após `git pull` e CI PASS)

```bash
cd "$HOME/frcaixinha-aistudio-mobile"
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py next
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py audit
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py secrets-plan
```

Compartilhar no chat **somente a saída desses comandos**, pois
eles imprimem nomes/estados e não os valores. Não copiar
`provider-public-inputs.json` nem detalhes secretos do painel.

O checklist termina com os estados:
`REAL_MAIL=OFF`, `USER_ACTIVATION=OFF`, `PIX_INBOUND=OFF`,
`PIX_OUTBOUND=OFF`, `OCI_DEPLOYMENT=NOT_ATTESTED`.
Nenhum desses flags pode ser alterado simplesmente porque os
13 campos de cadastro público estão completos.

## Próximas ações de desenvolvimento (não liberadas)

Depois de receber informação real de região, aplicativo,
domínio, provedor de e-mail e disponibilização da VM, construir
com evidência em staging:
1. backend de configuração OCI sem segredos de ambiente público;
2. worker de SMTP com outbox, auditoria e callback autenticado;
3. confirmação de e-mail e aceite individual em banco de staging
   com revalidação de contexto, expiração e idempotência;
4. OAuth Connect com troca real de código e refresh;
5. Orders Pix, webhook com assinatura e conciliação;
6. Payouts Pix apenas quando o MP confirmar formalmente.

Manter PR #2 aberta em DRAFT. Sem merge, migração local, pagamento
real, SMS/e-mail real ou criação de usuários sem autorização.
