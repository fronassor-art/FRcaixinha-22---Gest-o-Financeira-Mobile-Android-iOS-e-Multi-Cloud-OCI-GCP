# FR Finance AI Studio — M38013–M38029: revisão contratual isolada por sessão

Origem: M38012, commit bd2cbbf, 1.160 testes Python aprovados no Termux.

## M38013 — regressão legada de login corrigida
A validação geral do GitHub falhou no teste test_master_explicit_login_policy.py porque o cenário antigo esperava escolha implícita do primeiro de dois vínculos (Admin e Membro). Isso seria inseguro. O teste foi corrigido para exigir 409 quando dois vínculos tornam a escolha ambígua e preservar o retorno anterior apenas para uma identidade com exatamente um vínculo. Nenhum controle de autenticação foi relaxado.

## M38014–M38029 — isolamento de revisão documental
- Escopo puro vincula sessão (generation), identidade, perfil e caixinha. O administrador só pode revisar a sua própria caixinha; o Master não herda contexto financeiro e só prepara versão para tenant de destino informado.
- A tela descarta resultados tardios quando login, role, conta ou tenant muda. Respostas antigas nunca são pintadas no escopo novo.
- Catálogo de versões publicadas, texto canônico, SHA-256, resultado de comparação e mensagens de erro aparecem somente no mesmo escopo de origem.
- O carregamento de catálogo e de texto canônico exige sessão válida; a API continua autenticada e protegida por RLS.
- Nenhum aceite, assinatura, convite, e-mail, criação de conta ou vínculo é feito por essas verificações.
- Testes de 2 tenants, 2 contas, 3 papéis, mudança de geração, UUID inválido e sequência de respostas; regressões prévias do contrato permanecem obrigatórias.

## Como homologar
Execute o script Termux M37979 para tipagem alternativa TypeScript 6, mais os testes m25300_contract_review_ui_ci.test.ts, m38014_contract_review_scope_ci.test.ts e os testes Python m38001 e test_master_explicit_login_policy.py. SQL: nenhum. A CI oficial usa TypeScript 7 Linux.

## Gates
Não é uma tela de aceite de convidado nem prova de titularidade do e-mail. Os 20/7 gates e AT-01–AT-50 continuam pendentes. PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCAO=BLOCKED.
