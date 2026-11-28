# FR Finance AI Studio — M38330–M38369 | Correção DKIM Brevo TXT e ponte para leitura real

Checkpoint: M38329, commit 1dfb003, Termux 1.942 testes Python PASS, frontend TS6 PASS, DB original preservado. Projeto AI Studio apenas.

## Problema operacional corrigido

A implementação M38329 aceitava DKIM no formato v=DKIM1; k=rsa; p=... ou dois CNAME. Contudo a documentação oficial da API Brevo mostra um formato TXT sem v=DKIM1: k=rsa;p=<chave-pública>. Antes, a coleta da zona DNS filtrava exclusivamente v=dkim1;, de modo que um registro legítimo k=rsa;p=... era tratado como não observado, mesmo estando publicado.

Fontes oficiais:
- https://developers.brevo.com/docs/domain-authentication-and-verification
- https://help.brevo.com/hc/pt/articles/12163873383186-Autentique-seu-dom%C3%ADnio-com-a-Brevo-c%C3%B3digo-Brevo-DKIM-DMARC

## Implementação

- M38330–M38339: validador TXT aceita tanto v=DKIM1;... quanto k=rsa;p=...; valida tags duplicadas, tipos de chave, formato da chave pública e seletor exato. Continua reconhecendo dois CNAME como outra configuração válida.
- M38340–M38349: coletor público (backend/scripts/aistudio_mail_dns_readonly.py) seleciona tanto TXT do formato documentado quanto o formato com prefixo, e conta registros observados corretamente; nunca imprime conteúdo de DKIM, código Brevo, conta SMTP, segredo ou domínio de terceiros.
- M38350–M38359: testes parametrizados de versões válidas, formatos inválidos, material malformado, ausência de prova de assinatura e de autenticação real da conta.
- M38360–M38369: integração simulada do caminho live completo com DNS injetado, incluindo ambos os formatos DKIM, dois CNAME, consulta sem seletores, recusa sem autorização, erro de rede sanitizado e não vazamento de registros. CI não faz conexões externas.

## Próxima comprovação operacional

A consulta real aos registros públicos de frfinance.com.br deve ocorrer **no Termux com rede e autorização explícita**, não na CI e não automaticamente. Ela requer que FR_FINANCE_EMAIL_FROM esteja salvo no intake público e que dnspython esteja disponível no interpretador que invoca o script.

Para um DKIM TXT (apenas se o painel Brevo mostrar um seletor de TXT):
```sh
python backend/scripts/aistudio_mail_dns_readonly.py live AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY --selector mail
```
Para DKIM de dois CNAME (somente com os seletores exatos mostrados na Brevo):
```sh
python backend/scripts/aistudio_mail_dns_readonly.py live AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY --selector brevo1 --selector brevo2
```
Se o painel mostrar nomes diferentes, não assumir mail/brevo1/brevo2: substituir pelos nomes reais. Sem seletores, SPF/Brevo-code/DMARC podem ser observados, enquanto DKIM permanece NÃO CONSULTADO.

**Leituras de DNS não atestam** status Authenticated no painel da Brevo, assinatura/alinham. DKIM, STARTTLS autenticado, entrega, tratamento de bounce, titularidade ou consentimento. Ainda são necessários a confirmação no provedor e testes reais controlados antes da ativação. O DNS desta atualização **não foi lido externamente**.

Sem SQL novo, sem alterações OCI, sem acesso ao PostgreSQL original Termux 5433. EMAIL_REAL=OFF; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCAO=BLOCKED.
