# FR Finance AI Studio — Supermacropacote M27700–M28000

## Ponto de partida homologado

M27600 `7608521`: **192 testes Termux PASS**, AES-GCM disponível no
celular, `M19200_REGISTRY_HASHES=PASS`, 92 SQL íntegros e Pix
real DESATIVADO. PR #2 permanece aberta em **DRAFT**.
O código desta frente é o **AI Studio** e não deve ser misturado com
o projeto FRcaixinha 2.2 independente.

## Objetivo

Acabar com a repetição de bloqueios imprecisos: distinguir **quais dados
públicos o operador já pode preencher**, **quais segredos devem ser
instalados no OCI Vault** e **quais homologações ainda dependem de ação
efetiva da Oracle, do provedor de e-mail ou do Mercado Pago**.

Nenhum token, senha, DSN, segredo de webhook ou private key será
solicitado pelo CLI, armazenado no GitHub, enviado ao chatbot ou
incluído nos relatórios de auditoria.

### M27700 — Contrato de informações públicas

`backend/app/provider_intake_schema.py` valida os campos públicos,
sem rede, sem dinheiro, sem escrita no PostgreSQL e sem ativar serviços:

| Componente | Campo público | Onde descobrir |
| --- | --- | --- |
| Infra | `APP_URL` | Domínio HTTPS escolhido, depois de registrado |
| OCI | `OCI_REGION` | Console OCI, região da tenancy |
| OCI | `OCI_COMPARTMENT_OCID` | Identity & Security → Compartments |
| OCI | `OCI_INSTANCE_OCID` | Compute → Instances; apenas após provisionar |
| OCI | `OCI_VAULT_OCID` | Identity & Security → Vault |
| OCI | `OCI_DATABASE_HOST` | Host DNS do banco planejado, nunca IP local |
| E-mail | `SMTP_HOST` | Painel do provedor |
| E-mail | `SMTP_PORT` | `587` com STARTTLS |
| E-mail | `SMTP_USER` | Identificador de login SMTP, NÃO senha |
| E-mail | `FR_FINANCE_EMAIL_FROM` | Remetente homologado pelo domínio |
| MP | `MP_APPLICATION_ID` | Mercado Pago → Integrações → sua aplicação |
| MP | `MP_OAUTH_REDIRECT_URI` | Callback HTTPS exato registrado na aplicação |
| MP | `MP_WEBHOOK_URL` | Endpoint HTTPS público para Orders/mp-connect |

Os validadores bloqueiam URLs HTTP, localhost/IP direto, credenciais
embutidas em URL, query/fragment contendo token, injeções de cabeçalho
em endereços de e-mail, campos desconhecidos e indicadores para
ligar dinheiro/ativação.

## M27800 — Entrada local segura no Termux

`backend/scripts/aistudio_provider_intake.py` cria, fora do
checkout Git, o arquivo de metadados públicos:

`$HOME/.config/frfinance-aistudio/provider-public-inputs.json`

Ele é protegido com diretório `0700` e arquivo `0600`,
gravado atomicamente. Não armazena senhas/tokens. A ferramenta
não usa a porta local `5433`.

Depois de sincronizar o commit aprovado:

```bash
cd "$HOME/frcaixinha-aistudio-mobile"
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py init
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py fields
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py audit
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py plan
```

O comando `init` deve ser executado **uma única vez**; ele não
sobrescreve o arquivo se já existir.

Exemplo de preenchimento **somente de um dado não secreto**:

```bash
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py set OCI_REGION sa-saopaulo-1
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py audit
```

Substituir `OCI_REGION` pelo campo público desejado. Para
corrigir/remover um dado público:

```bash
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py unset OCI_REGION
```

Os comandos `audit` e `plan` produzem apenas nomes de campos
pendentes, estados de bloqueio e instruções; não imprimem os valores
que você forneceu.

**Nunca use `set` para um access token, password, secret, private
key, refresh token, DSN ou assinatura de webhook.** Nenhum campo
desses é suportado.

## M27900–M28000 — Evidência e matriz de implantação

`backend/app/operator_release_worklist.py` organiza sete gates:

1. `OCI_HOSTING` — VM, DNS, TLS, firewall, runtime SHA, RLS e backup;
2. `OCI_VAULT_IAM` — Vault, versions de segredo, instance principal,
   Dynamic Group e privilégio mínimo;
3. `MAIL_PROVIDER` — SPF/DKIM/DMARC, remetente, STARTTLS, worker,
   recibo e controle de reenvio;
4. `USER_ACTIVATION` — prova real de e-mail, MFA Master, dupla
   aprovação, aceite individual de contrato, uso único e revogação;
5. `MP_CONNECT` — OAuth authorization_code com PKCE, refresh,
   consentimento por administrador/tenant;
6. `PIX_INBOUND` — Orders API, `X-Idempotency-Key`, webhooks Orders,
   `x-signature`, conciliação com Livro-Razão;
7. `PIX_OUTBOUND` — habilitação comercial comprovada para Payouts/
   transferência Pix, limites, usuário/tenant proprietário e risco.

Mesmo com todos os dados públicos preenchidos, o status é
`PROVIDER_ATTESTATION_REQUIRED`, jamais `READY_FOR_REAL_MONEY`.
É obrigatório testar **cada provedor no ambiente correto** antes de
qualquer envio externo.

## O que o operador precisa obter dos provedores (sem revelar segredos)

### Oracle / OCI

- Confirmar tenancy, região, compartment, serviço Compute, rede e
  preço/plano compatível com orçamento;
- provisionar VM/container de staging, domínio DNS e HTTPS;
- definir Vault com três categorias separadas: credencial SMTP,
  segredos da aplicação Mercado Pago e chaves do backend;
- Dynamic Group e política IAM que permitam apenas o serviço
  correto ler cada segredo; referenciar apenas OCIDs e números de
  versão em configuração segura da VM;
- PostgreSQL de staging/produção próprios, SSL, roles segregadas,
  migrações homologadas e backups com restauração ensaiada.

O banco do Termux `frcaixinha_aistudio_dev` (porta `5433`)
não será transformado em banco público nem receberá SQL CI.

### E-mail

- Escolher provedor com SMTP autenticado + TLS e, idealmente,
  eventos de entrega/bounce com assinatura;
- verificar domínio/remetente, configurar SPF/DKIM/DMARC e confirmar
  limites/cotas e preço;
- cadastrar senha/API key **diretamente no Vault ou no ambiente
  seguro da VM**, jamais aqui ou no GitHub;
- comprovar envio para um endereço de teste autorizado, fila
  durável, timeout ambíguo/quarentena, token único e rollback;
- registrar prova de posse do destinatário, distinta da simples
  aceitação do SMTP.

### Mercado Pago

- Criar/identificar aplicação e modo teste/produção;
- obter **Application ID público** e registrar `redirect_uri` HTTPS
  idêntico ao utilizado na integração;
- guardar `Client Secret` em Vault; fazer OAuth Connect
  authorization_code + PKCE com consentimento do administrador de
  **cada caixinha** e refresh seguro; não compartilhar tokens;
- configurar webhooks HTTPS do tópico Orders (e `mp-connect`
  quando habilitado), guardando assinatura secreta no Vault;
- criar testes de Orders Pix com idempotência e validar notificações
  `x-signature` antes de consultar status de ordens;
- exigir confirmação comercial/documentação vigente para pagamentos
  de saída e limites de Payouts/transferências. **Não presumir**
  que o OAuth de recebimento autoriza transferências.

Referências oficiais:
- OAuth: https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation
- Orders Pix: https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/websites/pix
- Webhooks: https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications
- Payouts: https://www.mercadopago.com.br/developers/pt/docs/payouts/resources/api-endpoints

## O que permanece bloqueado corretamente

`MAIL_REAL=OFF`, `USER_ACTIVATION=OFF`,
`PIX_INBOUND=OFF`, `PIX_OUTBOUND=OFF`.
Qualquer prova sintética de CI, incluindo recibos de SMTP e tokens
M27100–M27600, NÃO prova entrega externa, titularidade real ou aceite.

Não criar novos Master, administradores ou membros reais; não executar
checkout Pix real, payout, liberação de crédito, cobranças ou
migrações locais. A PR #2 segue em rascunho.

### Como compartilhar progresso com o ChatGPT

Enviar somente a saída dos comandos `audit` e `plan`, com os
estados e nomes de campos, **sem copiar o JSON privado ou valores de
segredos**. Os resultados são suficientes para indicar qual passo
precisa de auxílio de configuração ou implementação.

Depois de cada integração ser instalada no provedor, testar
autenticidade de identidade, antifraude, logs redigidos e isolamento
por tenant em staging antes de discutir autorização real.
