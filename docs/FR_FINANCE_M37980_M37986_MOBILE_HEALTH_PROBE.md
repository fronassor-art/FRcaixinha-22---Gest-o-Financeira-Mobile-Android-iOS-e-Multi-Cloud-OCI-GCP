# FR Finance AI Studio — M37980–M37986 | Diagnóstico real de conectividade do APK

**Origem:** M37979 commit 69a9ce2, Termux 618 regressões Python e seis testes TypeScript PASS. Banco e SQL originais preservados.

## Implementação funcional, independente da VM OCI

1. M37980: módulo \`src/services/mobileBackendProbe.ts\` realiza uma consulta GET sem cookies/tokens à API FastAPI existente.
2. M37981: valida o endereço usando a mesma política de origem HTTPS/loopback do login.
3. M37982: exige resposta JSON de tamanho máximo 2 KiB, identidade declarada FR Finance, framework FastAPI e \`database_configured\` booleano.
4. M37983: requisição com \`credentials=omit\`, \`redirect=error\`, \`cache=no-store\` e timeout de cinco segundos.
5. M37984: a tela de login consulta o servidor primeiro e só depois o status da autenticação, sem indicar homologação real.
6. M37985: \`/api/health\` recebe cabeçalhos \`Cache-Control: no-store\` e \`Pragma: no-cache\` no middleware.
7. M37986: testes adversariais no cliente e na API para URL inválida, rede indisponível, 503, corpo adulterado, JSON inválido, banco ausente e ausência de credenciais.

## Interpretação correta

- \`BACKEND_ONLY\`: FastAPI respondeu, mas o banco foi declarado não configurado.
- \`BACKEND_WITH_DB_DECLARED\`: FastAPI respondeu e declarou configuração; **não prova** conexão SQL, posse do domínio, login com usuário, isolamento RLS ou implantação de produção.
- \`INVALID_RESPONSE\`, \`NETWORK_ERROR\`, \`URL_BLOCKED\`, \`HTTP_ERROR\`: nenhuma autorização é concedida.

O diagnóstico melhora o teste real no APK quando a API puder ser acessada. Ele não inicia FastAPI, OCI, Brevo, OAuth ou Pix; não faz SQL; não cadastra membros.

## Critérios de liberação que continuam pendentes

Todos os 20 gates técnicos e sete externos continuam exigindo provas independentes em staging; 147 cláusulas do contrato histórico e 57 itens vigentes ainda requerem evidência individual. Nenhum contrato ou instalação do banco foi alterado.

**Estado:** \`REAL_PIX=OFF\`, \`REAL_PAYMENTS=OFF\`, \`REAL_USERS=OFF\`, \`PRODUCTION=BLOCKED\`.
