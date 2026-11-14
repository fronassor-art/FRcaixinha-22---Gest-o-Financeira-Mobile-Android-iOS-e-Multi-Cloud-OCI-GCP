# FR Finance AI Studio — M38450–M38489 | Triagem da resolução DNS pública no Termux

**Origem:** M38449, commit 6c27cfc, 2.007 testes Python PASS, DNSPYTHON READY, remetente validado, consulta DNS real autorizada retornou DNS_RESOLVER / EXIT=2.

## Causa ainda não confirmada

O código anterior `_collect_public_dns` agrupou em erro DNS_RESOLVER quaisquer falhas ao inicializar o resolvedor ou receber/interpretar dados da rede. O resultado do Termux comprova que a leitura de metadados públicos do operador está válida, mas **não identifica** timeout, ausência de servidores configurados, SERVFAIL/REFUSED, NXDOMAIN ou problemas no TXT. Alterar DNS do sistema, publicar novamente SPF/DKIM ou declarar o domínio incorreto sem distinguir essas hipóteses seria prematuro.

## Implementação M38450–M38489

- M38450–M38459: `backend/app/mail_dns_transport_readonly.py` com avaliação pura dos resultados DNS sem qualquer rede, segredos ou conteúdo TXT. Traduz exceções para categorias fixas, sem exibir nomes de servidores, registros, mensagens de exceções ou endereços.
- M38460–M38469: `backend/scripts/aistudio_mail_dns_transport_probe.py`, diagnóstico de infraestrutura com subcomandos `offline`, `system`, `cloudflare`, `google`. Consulta exclusivamente dois nomes públicos fixos: TXT da raiz do domínio `frfinance.com.br` e TXT de `_dmarc.frfinance.com.br`. Sem seletores DKIM, e-mails ou tokens.
- M38470–M38479: `system` usa o resolvedor existente, nunca altera o sistema ou realiza fallback automático. `cloudflare` consulta 1.1.1.1 e `google` consulta 8.8.8.8, **somente com outra autorização explícita**; compartilhará apenas os dois nomes públicos consultados com o provedor DNS escolhido. A comparação permite distinguir configuração DNS local de uma falha percebida também em terceiros.
- M38480–M38489: testes CI offline com resolvedor injetado; validação de autorização antes de qualquer consulta, relatórios de timeout, SERVFAIL/REFUSED, NoResolverConfiguration, ausência de TXT/NXDOMAIN, exceção desconhecida, não vazamento e produção bloqueada.

## Passos do operador — sem alteração na rede

Primeiro, após homologação local da branch:

    python backend/scripts/aistudio_mail_dns_transport_probe.py offline

Depois, se continuar autorizada a leitura pública:

    python backend/scripts/aistudio_mail_dns_transport_probe.py system AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY

Interpretar as linhas `M38489_RESOLVER_STATUS`, `M38489_ROOT_TXT`, `M38489_DMARC_TXT`. A presença de TXT é um estado **observado em uma resposta** e NÃO uma autenticação da Brevo.

Somente se o resolvedor local apresentar falha ou timeout, optar por consulta externa à Cloudflare **explicitamente**:

    python backend/scripts/aistudio_mail_dns_transport_probe.py cloudflare AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY

Se o sistema falhar e a Cloudflare responder, investigar `/etc/resolv.conf` e a conectividade do Debian PRoot/Termux; não sobrescrever o arquivo sem conhecer a rede e o ambiente. Se os dois falharem, considerar bloqueio de DNS externo ou indisponibilidade de rede. Se ambos responderem mas `aistudio_mail_dns_readonly.py live ...` permanecer bloqueado, investigar separadamente a interpretação do TXT, sem imprimir valores.

## Limites de escopo

Este diagnóstico **não** lê o TXT integral, não comprova assinatura DKIM, não prova correspondência do código Brevo com a conta, não acessa SMTP, não altera o DNS, banco, OCI, GitHub Secrets nem cadastros. A consulta pública é feita somente no Termux do operador, nunca no CI. Mesmo uma resposta DNS positiva não liberta 20 gates operacionais ou 7 gates de provedores de produção.

EMAIL_REAL=OFF; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; DB_ORIGINAL_5433=PRESERVADO; MIGRACOES_LOCAIS=NONE; CLOUD_MUTATIONS=NONE; PRODUCTION=BLOCKED.
