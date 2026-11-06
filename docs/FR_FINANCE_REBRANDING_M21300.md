# FR Finance — M21300: nome comercial aprovado

## Marca escolhida
O usuário aprovou **FR Finance** como nome comercial do aplicativo e nome a ser informado na aplicação do **Mercado Pago Developers**. A alteração foi aplicada ao login, navbar, rodapé, texto Android, Capacitor, manifesto PWA, ícone SVG, título/descrição web, avisos, documentação introdutória e material de apresentação.

## Compatibilidade mantida
- **Não alterar** `com.frcaixinha.app` (applicationId, namespace, deep links), assinatura Android, versionCode e canal de atualização; o APK novo deve atualizar o anterior.
- Não renomear repositório, branch, PR, scripts Termux, banco PostgreSQL `frcaixinha_aistudio_dev` na porta 5433, funções SQL, roles, eventos de autenticação, headers `X-FRcaixinha-Client`, nomes de assets/ZIP de referência ou chaves de storage usadas por versões anteriores. Esses são identificadores técnicos históricos, não marca visível.
- Não confundir projeto AI Studio com o FR 2.2 independente. Os contratos antigos são documentação histórica e não sofrem substituição retroativa.
- A palavra "caixinha" ainda pode nomear o **tipo de grupo financeiro**, seus ciclos e módulos, sem identificar o produto comercial.
- Nome aprovado pelo usuário **não equivale a registro ou exclusividade de marca no INPI**.

## Mercado Pago
Em `https://www.mercadopago.com.br/developers/panel/app`, informar **FR Finance** como nome da nova aplicação. A aplicação deve ser criada ou alterada **manualmente** no painel pela conta autorizada. Nenhuma credencial/token foi acessado, criado, exposto ou modificado nesta alteração. O OAuth multiadmin, webhooks Orders, OCI Vault e fluxos financeiros reais continuam bloqueados aguardando configuração e homologação.

## Testes
`npx tsx src/tests/m21300_fr_finance_brand_ci.test.ts` e as verificações habituais CI Android/PostgreSQL. O banco local foi comprovado com 46 tabelas e 044 aplicada pelo usuário antes desta mudança; não há migrações novas.
