# FR Finance AI Studio — M38570–M38649 | Brevo SMTP STARTTLS/AUTH sem envio

## Base de evidência (11/11/2026)

- M38569, SHA `05fb874`: 2.137 testes Python PASS no Termux; frontend e GitHub em sincronia.
- O DNS público do domínio `frfinance.com.br` foi observado com SPF, DMARC e dois DKIM CNAME candidatos; isso **não comprova** a autenticação do domínio na conta Brevo.
- O código de consulta autenticada do provedor (GET domínio, M38530–M38569) foi testado offline, mas `BREVO_ACCOUNT_REAL=NOT_QUERIED`.
- Gates reais de envio, consentimento, Pix, usuários e produção continuam bloqueados.

## Novo alcance

Implementado o comando `backend/scripts/aistudio_brevo_smtp_auth_nosend.py` que verifica, quando explicitamente autorizado, somente:

1. Conexão fixa com `smtp-relay.brevo.com:587`, timeout de 12 s.
2. Resposta SMTP inicial e EHLO (esperadas 220 e 250).
3. Exigência explícita de STARTTLS antes de qualquer AUTH.
4. TLS com CA do sistema, verificação de hostname e mínimo TLS 1.2.
5. Novo EHLO após TLS e verificação da capacidade AUTH.
6. `SMTP.login()` com usuário SMTP Brevo e **chave SMTP**, nunca senha da conta ou chave API; exige resposta de sucesso 235.
7. Fechamento imediato da conexão sem `MAIL FROM`, `RCPT TO`, `DATA` ou qualquer envio.

Não há `sendmail`/`send_message`, envio de prova, inscrição de remetente, autenticação de domínio por API, registro de webhook, mutation de cloud, acesso PostgreSQL ou ativação de usuário. Uma tentativa AUTH pode constar nos logs do provedor, mas não altera sua configuração.

**Política de credenciais:** o teste não lê argumentos de senha, `.env`, intake, variáveis de ambiente ou arquivos. O operador fornece login e chave SMTP por prompts ocultos em TTY interativo. Nunca colar segredos no chat, em comandos shell, no GitHub ou em logs. Se falhar, imprime somente códigos fixos sem reproduzir respostas do servidor.

## Execução no Termux

No diretório raiz do repositório, após sincronizar:

```sh
python backend/scripts/aistudio_brevo_smtp_auth_nosend.py offline
python -m pytest -q -p no:cacheprovider backend/tests/test_m38570_brevo_smtp_auth_nosend_ci.py
```

O primeiro comando **não usa credenciais e não acessa a rede**. O segundo usa cliente SMTP falso e chave sintética.

### Opcional: leitura REAL da capacidade de autenticação, sem enviar mensagens

Somente quando o proprietário decidir realizar o teste interativo e tiver login/chave SMTP da conta Brevo (distintos da API key), no Termux:

```sh
python backend/scripts/aistudio_brevo_smtp_auth_nosend.py live AUTHORIZE_BREVO_SMTP_STARTTLS_AUTH_NO_SEND
```

Os prompts ocultos serão exibidos **no Termux**. Não executar por cron, GitHub Actions, agendadores ou em terminal não interativo. Se o teste der `CONFIRMED_FOR_THIS_SESSION_ONLY`, isso prova **apenas que aquela conta autenticou uma sessão SMTP via TLS no momento observado**, não que o e-mail chegará, terá DKIM alinhado, que o remetente está autorizado ou que o domínio Brevo está autenticado.

- Para checar o status **da conta de domínio**, usar o M38569 separado, com chave API apropriada; nunca substituir chave SMTP por chave API.
- Se a porta 587 estiver indisponível, investigar a restrição de rede em vez de desativar TLS ou acrescentar fallback silencioso.
- O fluxo de envio controlado e recebimento de mensagem continua **fora** deste pacote.

## Matriz de gates fechados

| Comprovação | Depois de sucesso SMTP AUTH |
|---|---|
| Login SMTP com STARTTLS | `CONFIRMED_FOR_THIS_SESSION_ONLY` |
| GET de domínio na conta Brevo | `NOT_ATTESTED_BY_SMTP` |
| Remetente válido | `NOT_ATTESTED` |
| Envio de e-mail real | `NONE` |
| Recebimento, DKIM e alinhamento | `NOT_TESTED` |
| Consentimento do destinatário | `NOT_ATTESTED` |
| Pix e pagamentos reais | `OFF` |
| Ativação de membros e administradores | `OFF` |
| Banco original, migrações e OCI | `UNTOUCHED` |
| Liberação da produção | `BLOCKED` |

## Etapas planejadas e executadas

- **M38570–M38579:** contrato de execução offline, autorização independente e prevenção de uso sem TTY.
- **M38580–M38589:** hostname/porta fixos, formato de credenciais e isolamento de segredos.
- **M38590–M38599:** handshake SMTP, STARTTLS com CA, EHLO pós-TLS, retorno AUTH.
- **M38600–M38609:** nenhuma transação de e-mail; fechamento em sucesso ou erro; sem integração com Pix/banco/cloud.
- **M38610–M38619:** códigos de diagnóstico fixos e bloqueios de produção.
- **M38620–M38629:** testes de erro, timeout, TLS ausente, credenciais inválidas e falhas.
- **M38630–M38639:** CI com SMTP sintético e sem secrets ou rede.
- **M38640–M38649:** documentação de operação e evidências, auditoria de liberações negativas.

Esta numeração agrupa trabalhos e testes; não representa 80 execuções de produção ou 80 resultados de homologação independentes.

## Referências oficiais Brevo

- https://help.brevo.com/hc/pt/articles/7924908994450-Envie-e-mails-transacionais-usando-o-Brevo-SMTP
- https://help.brevo.com/hc/pt/articles/10905415650322-Qual-porta-SMTP-devo-usar-Porta-587-465-ou-2525
- https://help.brevo.com/hc/pt/articles/7959631848850-Criar-e-gerenciar-suas-chaves-SMTP
