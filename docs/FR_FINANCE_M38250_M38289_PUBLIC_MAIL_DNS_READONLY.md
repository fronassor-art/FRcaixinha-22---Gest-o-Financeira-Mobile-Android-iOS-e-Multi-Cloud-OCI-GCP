# FR Finance AI Studio — M38250–M38289 | Diagnóstico público de SPF, DKIM e DMARC

Origem: M38249, commit 5e1d4b1, 1.784 testes Python PASS no Termux. A CI geral desse commit concluiu com sucesso. Projeto exclusivamente AI Studio.

## Motivação operacional
Os envios pelo Brevo dependem de identidade de domínio, SPF/DKIM/DMARC, remetente aprovado e SMTP/STARTTLS. O domínio frfinance.com.br e os e-mails de contato e suporte foram escolhidos, mas a publicação e a verificação dos registros de domínio ainda precisam de **prova externa real**. O M38250 fornece uma inspeção pública somente leitura que independe da VM OCI.

## Itens implementados
- M38250–M38259: política pura de snapshots DNS, estritamente tipada, com validação de texto, domínio, IPs falsos, SPF único e política terminal -all ou ~all.
- M38260–M38269: leitura conceitual de DMARC publicado em _dmarc.frfinance.com.br, rejeição de múltiplos registros, tags duplicadas e p=none ou pct inferior a 100 como prova de enforcement. Qualquer retorno é apenas diagnóstico.
- M38270–M38279: até dois seletores DKIM informados pelo operador, sem tentar adivinhar os nomes criados no Brevo; inspeciona CNAME ou TXT v=DKIM1 com chave pública. CNAME publicado NÃO prova, isoladamente, que a chave assinou uma mensagem.
- M38280–M38289: comando explicito de consulta live via dnspython opcional e intake público privado já existente em ~/.config/frfinance-aistudio/provider-public-inputs.json. Limita domínio consultado ao remetente @frfinance.com.br, não imprime registros completos nem dados do provedor, não acessa banco/OCI e não envia email. Testes CI usam apenas dados sintéticos.

## Comandos
Modo offline, sem DNS:
```sh
python backend/scripts/aistudio_mail_dns_readonly.py offline
```
Leitura pública real, somente se o operador quiser, usando o domínio do remetente já salvo no intake:
```sh
python backend/scripts/aistudio_mail_dns_readonly.py live AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY --selector SELETOR_DKIM_1 --selector SELETOR_DKIM_2
```
Substituir os seletores por **nomes realmente informados no painel Brevo**, apenas a parte anterior a ._domainkey.frfinance.com.br. Nunca fornecer chave privada, senha, token, DSN ou conteúdo TXT completo. Os placeholders acima não são nomes válidos de seletores (a verificação exige minúsculas e hífen). É permitido consultar sem seletores para obter SPF/DMARC, mantendo DKIM pendente.

O modo live requer biblioteca opcional dnspython; se indisponível, ele apenas imprime erro padronizado. A instalação do pacote opcional deve ser feita em ambiente isolado de teste, não no backend de produção. Essa dependência NÃO foi adicionada ao runtime da API.

## Limites e próximos passos reais
Uma consulta pública positiva indica existência e sintaxe dos registros naquele momento. Ainda faltam validação do remetente no Brevo, alinhamento SPF/DKIM/DMARC em mensagem real controlada, SMTP STARTTLS com credencial armazenada no Vault, webhook de bounce e prova de domínio. Nenhuma consulta habilita envio, usuários ou Pix. Respostas de erros remotos e valores de TXT nunca são impressos pelo CLI.

O relatório continua sem provas de 20 gates operacionais, 7 gates de provedor e 50 testes reais ponta a ponta. Sem novas migrações; PostgreSQL 5433 preservado; CLOUD_MUTATIONS=NONE, EMAIL_REAL=OFF, PIX_REAL=OFF, ACTIVATION_REAL=OFF, PRODUCTION=BLOCKED.
