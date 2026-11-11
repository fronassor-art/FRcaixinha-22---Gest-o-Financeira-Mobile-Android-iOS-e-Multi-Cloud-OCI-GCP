# FR Finance AI Studio — M38290–M38329 | Auditoria DNS alinhada à configuração real da Brevo

**Origem:** M38289, commit f4fa88d, 1.903 testes Python aprovados no Termux. Projeto exclusivamente AI Studio.

## Divergência identificada e corrigida

A política genérica M38289 marcava como bloqueio a ausência de SPF, o DMARC com p=none e o DKIM em TXT único. Essa interpretação não era apropriada ao provedor selecionado. Segundo a documentação oficial da Brevo (consultada em 11/11/2026), para autenticação do domínio são usados Brevo code TXT, DKIM (um TXT ou dois CNAME) e DMARC. SPF e MX não são obrigatórios para autenticação de domínio com a configuração compartilhada, e p=none pode ser usado inicialmente com relatório rua.

Fonte primária: https://help.brevo.com/hc/en-us/articles/12163873383186-Authenticate-your-domain-with-Brevo-Brevo-code-DKIM-DMARC

## M38290–M38329

- **M38290–M38299:** Política provider-aware (backend/app/brevo_sender_dns_policy.py), sem IO; domínio remetente fixo frfinance.com.br, TXT de código Brevo observado por padrão, sem registrar/imprimir seu valor ou alegar correspondência à conta.
- **M38300–M38309:** SPF ausente classificado como opcional no cenário compartilhado, SPF duplicado ou permissivo continua suspeito. DMARC p=none com rua é aceito como registro de monitoramento, claramente distinto de enforcement real; duplicação, sintaxe inválida e ausência de rua são reportadas.
- **M38310–M38319:** Suporte a **um TXT DKIM ou dois CNAME**, sem assumir que 2 CNAMEs são obrigatórios em toda conta. TXT com chave inválida, CNAME incompleto, duas TXT, formatos mistos ou seletores não consultados continuam pendentes.
- **M38320–M38329:** Integração à saída do comando original de DNS, sem mudar o modo de autorização explícita. Testes adversariais em CI, sem DNS real, SMTP, banco ou OCI.

## Comandos

Homologação offline sem rede (no Termux após sincronização):

    python backend/scripts/aistudio_mail_dns_readonly.py offline

Consulta DNS real **opcional e explicitamente autorizada**, após ter preenchido FR_FINANCE_EMAIL_FROM no intake público e instalado dnspython isoladamente:

    python backend/scripts/aistudio_mail_dns_readonly.py live AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY

Sem seletores, o resultado inspeciona o código Brevo e DMARC mas mantém DKIM pendente. Para verificar DKIM, acrescente exatamente um --selector NOME caso o painel Brevo mostre um TXT, ou dois --selector NOME1 --selector NOME2 se mostrar dois CNAME. Nunca informe senha, valor de TXT, token, chave privada ou API key.

## Critério de verdade

DNS_SHAPE_COMPLETE significa apenas que as **respostas públicas parecem ter as formas esperadas**, não que a conta Brevo autenticou o domínio. A validação real requer status Authenticated no painel Brevo, cabeçalhos de e-mail mostrando DKIM/DMARC alinhados, STARTTLS/autenticação em provedor, recebimento controlado, bounce e outbox transacional. Nenhum desses sinais foi atestado nesta atualização.

Sem migrações locais, alteração no banco PostgreSQL original porta 5433, alteração OCI, envio SMTP ou ativação Pix. EMAIL_REAL=OFF; PIX_REAL=OFF; ACTIVATION_REAL=OFF; PRODUCTION=BLOCKED.
