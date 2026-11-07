# FRcaixinha AI Studio Mobile — Pacote 14: Respostas HTTP seguras

Baseline: 4030dffdff55b1dcfaf3e5a1fbcc9e90369f2329
Branch atualizacao-ai-studio-9b46a63187, PR #2 Draft.

## Problema corrigido
Mensagens de erro não confiáveis podiam retornar objetos em vez de strings
e criar saídas [object Object], HTML ou texto extenso. Resposta HTTP 200
com JSON inválido podia gerar um SyntaxError genérico na interface.

## Entregas
- Política central de mensagens/códigos do backend: strings pequenas,
  sem quebras de linha, HTML e indicadores comuns de segredos.
- HTTP 401 tratado antes de ler JSON: revoga apenas a sessão corrente.
- HTTP 403, 503 e demais status mapeados para mensagens seguras.
- HTTP 200 com JSON inválido gera ApiResponseIntegrityError e não
  cria dados, não registra sucesso nem faz fallback para seed local.
- Durante parsing de falhas e sucesso, respostas da sessão anterior
  são descartadas; nenhum 401 antigo pode revogar login mais recente.
- CI com cenários sintéticos: malformed JSON 200, body 403 como objeto,
  503 indisponível com código, 500 com HTML perigoso, 401 tardio,
  sessão vigente revogada e POST financeiro sem retry.

## Limites e restrições
- Filtragem no cliente não substitui proteção de API, RBAC e PostgreSQL RLS.
- Nenhum cenário de teste cria pagamentos, saldos, usuários ou convites.
- Não foram feitas migrations, GRANT, edições em contas reais, alterações
  no appId/assinatura Android nem merge na main.
- Compilação por pacote, APK manual somente na versão 180, salvo risco
  crítico de segurança que exija inspeção antecipada.
