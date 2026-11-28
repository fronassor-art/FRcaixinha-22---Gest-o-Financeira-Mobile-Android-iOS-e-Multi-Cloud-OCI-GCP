# FR Finance AI Studio — M38490–M38529 | Consulta DNS real com resolvedor público explícito, sem alterar o sistema

Checkpoint inicial: M38489, commit c8c3c57, 2.049 testes Python aprovados no Termux. O novo diagnóstico REAL indicou `M38489_RESOLVER_STATUS=SYSTEM_RESOLVER_NOT_CONFIGURED`, com zero consultas DNS realizadas. Isso **não atesta** publicação incorreta do domínio ou indisponibilidade da Brevo. PostgreSQL original preservado, produção bloqueada.

## Resolução operacional do bloqueio

O Debian/PRoot no Termux não fornece ao dnspython um resolvedor de sistema utilizável. Em vez de sobrescrever `/etc/resolv.conf` ou usar fallback implícito, o comando de verificação da Brevo oferece escolha explícita de servidores públicos limitados a dois endereços fixos:

- Padrão: `--resolver system`, exige `AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY`. Mantém o comportamento anterior.
- Cloudflare: `--resolver cloudflare`, usa `Resolver(configure=False)` com o IP fixo `1.1.1.1`. Exige `AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY`.
- Google Public DNS: `--resolver google`, usa `Resolver(configure=False)` com o IP fixo `8.8.8.8`. Exige **a mesma autorização distinta de terceiros**.

O domínio pesquisado é **apenas** `frfinance.com.br`, seu `_dmarc` e, se fornecidos explicitamente, até dois seletores `._domainkey.frfinance.com.br`. Nenhum endereço arbitrário, token de login, senha, chave privada ou recurso da OCI pode ser consultado por esta ferramenta.

## Entrega M38490–M38529

- M38490–M38499: coletor `_collect_public_dns` com resolvedor escolhido explicitamente, sem alterar Android, Debian, PRoot ou `/etc/resolv.conf`. Default anterior preservado para ferramentas e testes legados.
- M38500–M38509: autorização separada por modo e validação de nome de domínio, seletores e tipo de entrada **antes** de criar qualquer resolvedor. Nunca ocorre fallback automático do sistema para terceiros.
- M38510–M38519: continuação do diagnóstico Brevo completo, com indicação `M38529_RESOLVER_MODE` e `M38529_THIRD_PARTY_PUBLIC_DNS`. Respostas TXT são usadas somente em memória e convertidas em sinais redigidos. Dados originais não são impressos.
- M38520–M38529: testes automatizados com implementação falsa de `dns.resolver`, exercitando caminho completo do CLI para Cloudflare e Google, segurança de autorizações, domínio e seletores limitados, erro DNS sanitizado e nenhuma chamada de rede na CI.

## Próxima operação no Termux

Após CI e sincronização, a consulta **real** poderá ser expressamente autorizada:

```sh
python backend/scripts/aistudio_mail_dns_readonly.py live \
  AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY \
  --resolver cloudflare
```

O comando envia os nomes **públicos** do domínio à Cloudflare. Ele não configura DNS do sistema e não faz alterações locais, mas é uma nova conexão a um terceiro: escolha do operador.

Sem seletores, o diagnóstico considera DKIM `NOT_QUERIED`. Para inspecionar DKIM, adicione os seletores exatos que o painel Brevo indicar, sem compartilhar os valores TXT; TXT único ou dois CNAMEs podem ser válidos conforme o método cadastrado.

Se o provedor DNS não responder, a saída continuará com `M38409_FAILURE_STAGE=DNS_RESOLVER`; teste Google Public DNS explicitamente apenas depois de avaliar a conectividade. Se responder, observe `M38329_BREVO_CODE_RECORD`, `M38329_DMARC_STATUS` e `M38329_DNS_SHAPE_COMPLETE`, lembrando que registro observado não equivale à autenticação efetiva da conta Brevo.

## Limites invioláveis

Sem migrações, sem banco 5433, sem OCI write, sem SMTP, sem envio real, sem Pix, sem pagamentos e sem ativar administradores/membros. A auditoria contratual mantém 57 requisitos documentais pendentes, 20 gates operacionais e 7 de provedores sem evidência de produção. EMAIL_REAL=OFF, PIX_REAL=OFF, ATIVACAO_REAL=OFF, PRODUCAO=BLOCKED.
