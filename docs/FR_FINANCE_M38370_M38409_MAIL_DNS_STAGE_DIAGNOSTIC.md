# FR Finance AI Studio — M38370–M38409 | Diagnóstico do bloqueio DNS real sem exposição de dados

Origem: M38369, commit 2bdbe3b, **1.975 testes Python PASS no Termux**, frontend validado, dnspython disponível.

## Defeito identificado

O comando manual autorizado:

    python backend/scripts/aistudio_mail_dns_readonly.py live AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY

retornou M38289_MAIL_DNS=BLOCKED_INPUT_OR_DNS_QUERY. O código anterior juntava indiscriminadamente falhas de acesso ao intake, remetente ausente, consulta DNS e avaliação sintática. Por isso, **esse erro não prova que os registros de frfinance.com.br estejam ausentes**.

## Implementação

- M38370–M38379: novo subcomando `diagnose`. **Sem conexão DNS**, apenas verifica que o manifesto privado de identificadores públicos é legível com permissões válidas, que o campo FR_FINANCE_EMAIL_FROM existe e é sintaticamente coerente com frfinance.com.br, e que dnspython está disponível. Não imprime o arquivo, o remetente nem valores de registros.
- M38380–M38389: saída com códigos de condição seguros: PUBLIC_INTAKE_MISSING_OR_INVALID, EMAIL_FROM_NOT_CONFIGURED, EMAIL_FROM_INVALID, EMAIL_FROM_DOMAIN_MISMATCH, DNSPYTHON_NOT_INSTALLED, DNSPYTHON_IMPORT_FAILED ou READY_FOR_EXPLICIT_PUBLIC_DNS_READ.
- M38390–M38399: diagnóstico do modo live dividido em estágios PUBLIC_INTAKE, DNS_RESOLVER ou DNS_RESPONSE_POLICY. Mantém a mensagem anterior M38289_MAIL_DNS para compatibilidade e oculta exceções, nomes DNS completos e dados sensíveis.
- M38400–M38409: CI de subcomando offline sem DNS, arquivo com permissão incorreta, remetente ausente, domínio divergente, dnspython injetado, recusa sem autorização, falhas de rede/validação com erros mascarados e compatibilidade com as suítes M38250/M38290/M38330.

## Como executar após sincronização

1. **Diagnóstico local, sem consultas DNS externas**:

    python backend/scripts/aistudio_mail_dns_readonly.py diagnose

2. Se resultar EMAIL_FROM_NOT_CONFIGURED e o arquivo do intake existir, configurar APENAS o endereço de remetente já decidido:

    python backend/scripts/aistudio_provider_intake.py set FR_FINANCE_EMAIL_FROM contato@frfinance.com.br

3. Se resultar PUBLIC_INTAKE_MISSING_OR_INVALID, examinar primeiro se existe e se as permissões são adequadas. Para configuração inexistente, o operador pode executar o comando original `init` (cria somente o manifesto público fora do Git e falha se já existir). **Nunca usar init para sobrescrever configuração existente.** Não usar chmod indiscriminado sem avaliar proprietário e diretório.

4. Quando o diagnóstico mostrar READY_FOR_EXPLICIT_PUBLIC_DNS_READ, executar opcionalmente:

    python backend/scripts/aistudio_mail_dns_readonly.py live AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY

Com seletores DKIM fornecidos **exatamente pela Brevo**, usar `--selector` para observar TXT ou CNAME. Sem seletores, DKIM permanece não consultado. O comando live é somente leitura pública e não acessa SMTP, banco nem nuvem.

## Garantias

O preflight offline não atesta DNS. Um status DNS real observado **não comprova** autenticação da conta Brevo, entrega ou assinatura e não liga envio de e-mail nem ativação de usuário. Esta atualização mantém 20 gates operacionais e 7 de provedor sem evidência real suficiente; mesmo quando o DNS funcionar, exigem-se validações independentes.

Sem alterações no PostgreSQL original porta 5433, sem migrações SQL, OCI, SMTP, Pix ou ativação. DNS_REAL=NOT_ATTESTED_UNTIL_LIVE; EMAIL_REAL=OFF; PIX_REAL=OFF; REAL_USERS=OFF; PRODUCTION=BLOCKED.
