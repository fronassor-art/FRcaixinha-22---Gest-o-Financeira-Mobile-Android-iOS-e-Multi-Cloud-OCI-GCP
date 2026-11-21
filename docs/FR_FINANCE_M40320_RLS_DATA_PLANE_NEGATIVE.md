# FR Finance M40320 — validação negativa de RLS no banco original (sem VM)

## Contexto e checkpoint

O operador confirmou no **Termux original**, em 17/11/2026, o M40310 `PASS_EXTENDED_CATALOG_METADATA_ONLY`: PostgreSQL 18 original 127.0.0.1:5433, banco `frcaixinha_aistudio_dev`, 6 tabelas FORCE RLS, 16 políticas corretas, 5 triggers SQL111 e privilégios mínimos do papel `frc_ai_app`. O M40310 concluiu com `DIAGNOSTIC_EXIT=0`, sem escritas e sem reiniciar PostgreSQL/FastAPI.

## Reutilização: uma só implementação no M39034

O projeto já possuía `backend/scripts/frfinance_m39034_rls_api_offline.py`, capaz de mudar para o **papel real `frc_ai_app`** com `SET LOCAL ROLE` numa transação `READ ONLY` na conexão ao banco original via `frc_ai_owner`. Não criar script ou banco paralelo. A extensão M40320 realiza as seguintes melhorias dentro desse mesmo script:

- Remove a contagem legada de **53 tabelas totais**, que podia bloquear falsamente após outras migrações legítimas. Confirma a presença das **seis tabelas necessárias** em vez disso.
- Mantém `row_security_active` verdadeiro em todas as seis tabelas depois da troca para `frc_ai_app`.
- Mantém a conferência de contagens zero no papel de aplicativo com contexto ausente e com ID fictício de membro.
- Acrescenta **quatro situações negativas adicionais**, sob o mesmo papel e a mesma conexão: administrador com ID de caixinha inexistente, membro de outra caixinha fictícia, Master sem caixinha e sessão com contexto vazio após troca de papel. São **36 consultas SELECT COUNT** no total, sem exibir nem copiar linhas de usuário.
- Falso positivo é bloqueado: se qualquer situação devolver uma linha visível, retorna `BLOCKED`. Não envia nenhum POST de aplicativo, não cria sessão, não grava tabela, não chama OCI.

**Limite da prova:** os IDs fictícios podem não corresponder a nenhum registro, e tabelas vazias também retornam zero. Portanto, o resultado é uma **prova negativa sob papel real em 6 tabelas, não comprovação de acesso positivo ou do isolamento integral entre duas caixinhas ativas**. Esta última requer autorização/sessões adequadas e não é inferida.

## Execução no ambiente original

Depois de CI e sincronização fast-forward do GitHub no **Termux nativo**, o M39034 deve ser executado com a versão Python/psycopg **já existente e homologada no Debian PRoot**, usando **o mesmo** caminho original do projeto: `/data/data/com.termux/files/home/fr-finance`. Não instalar pacotes, não criar venv, não atualizar serviços ou banco.

O pré-verificador exige `AI_STUDIO_APPROVED_SHA` igual ao commit atual e referência remota `origin/atualizacao-ai-studio-9b46a63187` no mesmo commit. Se qualquer identidade ou senha falhar, interromper sem criar role, reiniciar serviço ou recriar banco. A única senha solicitada é a preexistente `frc_ai_owner`, ocultada. Nenhuma senha deve ser compartilhada no chat.

## Produção e governança

Este pacote altera **apenas o verificador anterior M39034, seu arquivo de testes, CI e documentação**. **MIGRATIONS=NONE**, `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`. A VM OCI ainda não existe segundo o operador, e a PR #2 permanece Draft. FR Caixinha 2.2 permanece isolado.
