# FR Finance M41050 — contexto SQL de sessão assinado (protótipo NO-GO)

Data-base do código: M41040, HEAD 72a9a7f654da. Escopo exclusivo de laboratório descartável PostgreSQL 18 e testes offline. O pacote não altera rotas da aplicação, migrations, runtime, chaves reais ou política de produção.

## Mapeamento de requisitos

CP26-0019 exige sessão verificada e segregação de papéis e tenants. CP26-0003 e CP26-0004 exigem que Master não alcance dados privados dos tenants e que Admin/Membro permaneçam isolados. CP26-0061 e CP26-0062 exigem contexto de API e validação RLS em leitura e escrita. A matriz de 330 IDs e 2.310 etapas permanece intacta; este pacote é evidência de engenharia em laboratório, não aceite independente ou gate de produção.

## O que o experimento verifica

A reprodução M40570 mostra que app.current_role e app.current_user_id são valores SQL que o papel de aplicação pode definir. O fixture M41050 mantém uma tabela de baseline vulnerável apenas para repetir esse comportamento com dados sintéticos. A tabela protegida usa a identidade derivada de um capability aleatório cuja impressão digital está armazenada no PostgreSQL; a aplicação não escolhe user, papel ou tenant a partir dos GUCs antigos.

O código canônico assina, fora do SQL, session_id, user_id, role, tenant, nonce, expiração e escopo READ_ONLY por HMAC-SHA-256. Uma função SECURITY DEFINER no fixture aceita somente a role emissora e verifica a prova contra material de verificação em tabela inacessível às roles emissora e aplicação. O nonce é consumido por chave única dentro da transação; a função devolve um capability aleatório de curta duração, e o banco armazena somente seu hash. O RLS consulta claims associados a esse capability, ignora os GUCs antigos e confere papel, usuário, tenant, escopo, revogação e expiração.

A suíte PostgreSQL 18 descartável verifica falsificação direta de GUC, login emissor sem prova, alteração de claims assinados, expiração, replay concorrente, revogação, cruzamento entre tenants e negação de acesso do Master a linhas financeiras de membro. As credenciais e a chave são fictícias e geradas apenas no job efêmero.

## Limites remanescentes

- O material de verificação HMAC reside no fixture PostgreSQL. Owner/superuser pode ler ou trocar a chave e executar código privilegiado; esta ameaça permanece aberta. O protótipo não apresenta cofre, KMS/HSM, rotação de chaves ou custódia independente atestada.
- Não há serviço emissor real nem processo/UID/host separado validado. A chave no teste é mantida pelo harness de CI; isso não prova isolamento operacional do signer.
- O capability é um segredo bearer para a sessão assinada. SQL arbitrário na própria conexão consegue ler o GUC do capability e agir dentro da identidade, tenant e escopo daquela sessão enquanto estiver válido. Ele não permite trocar claims sem nova prova válida; vazamento, replay de acesso permitido e comprometimento do processo continuam riscos.
- O mecanismo existe somente em código de laboratório. A aplicação real ainda usa a fronteira GUC histórica; nenhuma rota foi conectada ao helper.
- Não é um desenho revisado independentemente nem uma candidata de migration. Não usar este fixture como SQL112/113 nem aplicar SQL ao banco original.
- Nenhum ciclo foi aberto e nenhum pagamento, convite, usuário ou comunicação real foi criado.

## Resultado e controles

M41050 pode reduzir a falsificação de identidade em um canal SQL separado se integrado a um signer verdadeiramente isolado e a chaves administradas fora do banco. A evidência atual não basta para substituir a autenticação de produção, remover M40840 NO-GO, remover M40930 HTTP 503 ou fechar a issue #5.

CI do pacote: pytest offline + PostgreSQL 18 descartável. Produção continua BLOCKED. SQL local, migrations, conexões ao banco autoritativo, reinícios e reloads são NONE. PIX_REAL, PAGAMENTOS_REAIS, ATIVACAO_REAL e comunicações reais permanecem OFF.
