# FR Finance AI Studio — M38410–M38449 | Código Brevo DNS em dois formatos

Origem: M38409, commit 6073994, 1.988 testes Python PASS no Termux; preflight local: READY_FOR_EXPLICIT_PUBLIC_DNS_READ. Banco original PostgreSQL 5433 preservado.

## Divergência documental encontrada

A documentação oficial da Brevo apresenta dois formatos de TXT de verificação de domínio:
- `brevo-code:...`: exemplos em https://developers.brevo.com/docs/domain-creation-and-management
- `brevo-code=...`: exemplos em https://developers.brevo.com/reference/get-domain-configuration

Antes, o validador M38290 considerava apenas o delimitador dois-pontos; uma observação real com sinal de igual apareceria como `BREVO_CODE_NOT_OBSERVED_OR_INVALID`, apesar de poder ser legítima. Essa correção não modifica nenhuma configuração de DNS nem autentica a conta.

## Entrega M38410–M38449

- M38410–M38419: reconhecer ambos os separadores na identificação de candidatos, com validação estrita do sufixo e sem imprimir o código de domínio.
- M38420–M38429: detectar duplicatas inclusive entre formatos diferentes, manter falhas de códigos ausentes ou inválidos como bloqueio e impedir qualquer inferência de controle da conta.
- M38430–M38439: testes parametrizados sobre formatos documentados, duplicidades, entradas inválidas e ausência de provas operacionais.
- M38440–M38449: testes com o comando `live` e DNS injetado (nenhuma conexão), assegurando que o código, TXT DKIM e eventuais segredos nunca sejam expostos pela saída.

## Próximo comando operacional, após homologação offline no Termux

Como `M38409_PREFLIGHT=READY_FOR_EXPLICIT_PUBLIC_DNS_READ`, o operador pode **autorizar novamente** a inspeção DNS pública:

```sh
python backend/scripts/aistudio_mail_dns_readonly.py live AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY
```

O comando informa agora `M38409_FAILURE_STAGE` no caso de bloqueio. Se der `DNS_RESOLVER`, investigar a resolução via Termux sem imprimir TXT; se `DNS_RESPONSE_POLICY`, investigar o formato observado, sem publicar código Brevo; se `PUBLIC_INTAKE`, investigar o manifesto local. Sem seletores DKIM informados pelo painel Brevo, só o código Brevo, SPF e DMARC são consultados.

Uma resposta pública com TXT não prova autenticação da conta Brevo, SMTP, domínio controlado, entrega, consentimento, licença ou prontidão de produção. Ainda exigirá confirmação no painel Brevo e testes externos controlados.

Sem SQL, sem migrações locais, sem OCI/SMTP/Pix, sem alterações de usuários. EMAIL_REAL=OFF; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCAO=BLOCKED.
