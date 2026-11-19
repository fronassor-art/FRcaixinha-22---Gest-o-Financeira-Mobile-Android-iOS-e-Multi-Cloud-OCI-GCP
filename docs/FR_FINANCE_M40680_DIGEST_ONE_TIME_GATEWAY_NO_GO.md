# FR Finance M40680 — gateway HTTP com resumo de sessão e ticket de uso único (PROTÓTIPO)

**Escopo: CI GitHub Actions PostgreSQL 18 descartável. Nenhuma alteração nas rotas reais. Produção: NO-GO.**

## Problema que M40680 tenta estudar

O M40670 passou um Bearer bruto a uma função SQL sintética, o que aumenta a superfície de exposição em logs de queries, extensões e diagnóstico. M40680 busca retirar o **Bearer bruto dos parâmetros SQL** e separar autenticação da consulta financeira.

## Prova de conceito

1. Em uma aplicação ASGI inteiramente sintética, o backend recebe Bearer e calcula SHA-256 em memória Python. O token bruto não é repassado ao SQL.
2. A conexão SQL **de autenticação** usa credencial distinta e somente pode invocar uma função com o **resumo de sessão** e tenant. Ela verifica existência de sessão, expiração, revogação, conta ACTIVE, papel ativo e vínculo ATIVA; emite um ticket aleatório de 256 bits com TTL de 30 segundos.
3. A conexão SQL **financeira**, com papel separado e sem SELECT nas tabelas protegidas, só pode consumir o ticket em função `SECURITY DEFINER` restrita, de escopo fixo. `UPDATE ... WHERE used_at IS NULL ... RETURNING` assegura consumo atômico, seguido de nova checagem de sessão, vínculo e tenant antes do SELECT.
4. O caminho antigo de função sintética com Bearer é explicitamente revogado ao papel financeiro no fixture. Variáveis GUC, cabeçalhos de suposto papel ou tenant não determinam identidade.

Os testes adversariais sintéticos devem recusar leitura de tabelas, `SET ROLE` proprietário, emissão de ticket pelo papel financeiro, consumo pelo papel de autenticação, repetição de ticket, uso em outro tenant, sessão revogada depois da emissão, ticket expirado, sessão Master, cross-tenant e token inválido.

## Limitações e riscos restantes

**Esse protótipo não prova ausência de credenciais sensíveis em SQL.** O hash SHA-256 do Bearer na conexão de autenticação torna-se **equivalente a uma credencial de emissão** caso a credencial/papel autenticador seja comprometida. O ticket temporário no SQL financeiro também é uma credencial reaproveitável por invasor enquanto não consumida, mesmo com TTL; logs ou extensões podem capturá-lo. É necessário estudar proof-of-possession, não-exportabilidade, auditar logs, parâmetros, telemetria, extensões, buffer/pool e exposição por operador com permissões no DB. Concorrência real, reuso, falhas entre emissão e consumo, rotação e desligamento de papéis devem passar por auditoria independente. A atribuição e separação entre auth e financeiro devem ser verificadas no sistema real, pois a execução de SQL arbitrário sob o papel de autenticação ainda representa fronteira crítica.

O experimento utiliza apenas papéis, sessões, registros e credenciais **fictícios** em banco **descartável :55437**. Não houve modificação das funções, migrations, roles ou bancos originais da aplicação, tampouco implantação de endpoints.

**Faltam:** integração com `get_current_session` no FastAPI original, vínculo com bearer real, análise de sessões multitenant em concorrência, funções de escrita, inventário dos privilégios de todos os caminhos SQL, rate limiting e segurança de logs. A exposição GUC spoof nos acessos existentes continua **NOT_REMEDIATED**. O FastAPI em execução no Termux permanece **não atestado**.

## Guardas imutáveis

`M40680_ORIGINAL_PG_5433=NOT_ACCESSED`; `M40680_LOCAL_DB_WRITES=NONE`; `M40680_LOCAL_MIGRATIONS=NONE`; `M40680_REAL_FASTAPI_ROUTES=NOT_MODIFIED`; `M40680_DIGEST_AND_TICKET_LOG_RISK=NOT_REMEDIATED`. `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.

Nenhuma sincronização com Termux ou migração no banco original sem validação e revisão específicas. PR #2 deve permanecer rascunho.
