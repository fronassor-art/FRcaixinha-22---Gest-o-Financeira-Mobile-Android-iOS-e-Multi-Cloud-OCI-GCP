# FR Finance M40630 — auditoria de privilégios SQL e fronteira GUC

**18/11/2026 — Base M40620 \`bed1d5f329bf65964398d7941bb766805a418c1e\`, PR #2 Draft. Produção NO-GO.**

## Problema que permanece

M40610 verificou a procedência de sessão HTTP antes de obter uma conexão financeira. M40620 impediu novas chamadas SQL dinâmicas diretas nos 25 roteadores auditados, preservando um auxiliar literal de homologação. **Esses controles não tornam confiáveis os valores \`app.current_role\` e \`app.current_user_id\` diante de um executor SQL arbitrário já autenticado como papel app.** O M40570 provou tal fronteira em fixture descartável; não provou bypass HTTP.

## Cobertura M40630

Novo job PostgreSQL 18 descartável verifica as permissões concretas de papéis sintéticos, incluindo SUPERUSER, BYPASSRLS, CREATEDB, CREATEROLE, LOGIN, RLS/FORCE RLS na tabela fictícia de revisão SaaS, privilégios de SELECT/INSERT vs UPDATE/DELETE/TRUNCATE e EXECUTE sobre a função de divulgação. Em seguida, confirma que o papel de aplicação, **mesmo sem privilégios de administração do PostgreSQL**, ainda pode definir custom GUCs e forjar a identidade fictícia Master no mesmo canal SQL. Essa prova usa somente UUIDs e linhas sintéticas, sem credenciais reais ou migrações locais.

Resultado esperado: ACL/RLS são camadas relevantes, mas o desenho atual **não é uma atestação de identidade independente do contexto SQL**. O resultado verde da CI é uma confirmação de comportamento e da exposição remanescente, nunca um \`GO\`.

## Próxima etapa necessária, sujeita a revisão e autorização explícita

Projetar um canal de consulta protegido contra SQL arbitrário, por exemplo com papéis e funções PostgreSQL de autoridade delimitada, levando em conta privilégios \`EXECUTE\`, \`SECURITY DEFINER\`, conexões de runtime separadas, risco de funções invocáveis e efeitos de \`SET ROLE\`; rodar prova negativa em PG18 descartável. Somente após revisão de arquitetura, teste de integração com bearer e consentimento explícito para migração no PostgreSQL original considerar produção. Não usar GUC simples como prova de identidade.

**Ambientes locais preservados:** FR Finance PG18 \`frcaixinha_aistudio_dev\` porta 5433, FR Caixinha 2.2 independente. Sem aplicação de SQL local, reinício FastAPI/PostgreSQL, migrações, comunicações, Pix ou pagamentos reais. \`PIX_REAL=OFF\`, \`PAGAMENTOS_REAIS=OFF\`, \`ATIVACAO_REAL=OFF\`, \`PRODUCTION=BLOCKED\`.

## Revisão da CI: INSERT restrito por coluna

A primeira execução do M40630 expôs uma incorreção **no teste**, não uma falha de permissão: SQL113 concede INSERT apenas em 14 colunas nomeadas, portanto `has_table_privilege(...,'INSERT')` deve retornar falso. O teste foi ajustado para exigir ausência de INSERT geral, verificar as 14 colunas permitidas, bloquear INSERT direto em `id` e `created_at` e rejeitar INSERT no papel de autenticação. Isso preserva a implementação SQL113 e melhora a precisão do diagnóstico.

## Validação da fronteira de confiança após correção de CI

A execução descartável pós-revisão de ACL passou nas etapas de papéis mínimos, FORCE RLS, permissões de colunas, EXECUTE e **reproduziu GUC spoofing com papel app sintético**. A execução finalizou com erro de sintaxe em `RESET app.current_role` durante a limpeza, pois o identificador `current_role` é um token reservado nesse contexto; a limpeza foi alterada para `set_config(..., '', false)` e será novamente verificada exclusivamente na CI. O achado de risco continua NO-GO.
