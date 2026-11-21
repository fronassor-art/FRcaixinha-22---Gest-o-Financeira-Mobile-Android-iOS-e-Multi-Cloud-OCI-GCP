# FR Finance M39076 — campanhas para membros e oportunidades no Android

## Diagnóstico confirmado no repositório AI Studio (13/11/2026)
A implementação prévia de crédito especial `src/components/SpecialCreditView.tsx` e
as rotas `/api/v1/tenants/{tenant_id}/special-credit/*` estavam presentes.
A ausência no APK decorreu de não incluir a página em `src/App.tsx`
e não cadastrar essas abas na lista `src/services/roleScope.ts`.
A M39075 corrigiu a preservação da edição ao alternar entre aplicativos.

## Correção
1. TENANT_ADMIN: nova seção **Campanhas para Membros** em `Mais` e
   botão de acesso no painel principal da caixinha.
2. TENANT_MEMBER: nova seção **Minhas Oportunidades** em `Mais` e
   acesso rápido no painel individual.
3. MASTER: não recebe as abas e não pode consultar campanhas de crédito
   dos tenants; não misturar **promoções SaaS do Master** com
   **campanhas de crédito do administrador da caixinha**.
4. Interface existente reutilizada: seleção de membros com permissão
   individual, teto de simulação, validade, justificativa de risco,
   criação/publicação interna/cancelamento de campanhas, e leitura de
   oportunidades e respostas por membro.
5. Acesso protegido em três camadas: lista de abas autorizadas,
   condição de papel na renderização da página, e API vinculada
   à sessão e ao tenant com RLS.
6. Não cria propostas aprovadas, empréstimos, desembolsos, Pix,
   comunicação externa ou notificações push reais.

## Gate de funcionamento
A interface é visível após a atualização do APK, mas a operação
de criação/publicação só funciona **se o servidor de homologação local**
tiver SQL110 e SQL111 comprovadamente aplicadas e
`FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES` habilitado no processo FastAPI
**após inspeção e autorização operacionais específicas**. Por padrão,
o gate permanece OFF; a tela informa a indisponibilidade e não inventa
membros ou campanhas. O workflow do Android mantém
`FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO`; isto não habilita recursos
no backend nem autoriza produção.

Nenhuma migração local é executada pela CI ou pelo APK. SQL110/111
e o banco original da FR Caixinha 2.2 não são alterados.
O aplicativo acessa apenas o backend local existente quando autenticado.
Credenciais e tokens não são persistidos offline.

## Testes
- `src/tests/m39076_tenant_campaigns_navigation_ci.test.ts` valida
  entradas de navegação, botões, RBAC frontend e gate backend;
- `src/tests/m39020_credit_push_ui_ci.test.ts` e
  `src/tests/m39048_credit_auth_boundary_ci.test.ts` mantêm
  testes de isolamento de sessões e infraestrutura;
- A CI da compilação principal valida o certificado original, o
  mesmo package ID e código de versão Android crescente.

## Homologação no aparelho
- Instalar APK M39076 assinado como atualização do aplicativo anterior,
  sem desinstalar.
- Perfil Administrador: tela inicial > **Campanhas para membros**,
  ou **Mais > Campanhas para Membros**; verificar formulário de crédito
  especial e mensagens de homologação, sem efetuar concessões reais.
- Perfil Membro: tela inicial > **Minhas oportunidades**, ou
  **Mais > Minhas Oportunidades**; somente destinatário pode consultar
  suas ofertas, se publicadas e habilitadas.
- Perfil Master: somente suas **Promoções SaaS**, nunca campanhas privadas
  do administrador da caixinha.
- Se aparecer "Crédito Especial ainda não habilitado para homologação",
  preservar as proteções e inspecionar SQL110/111 e o gate, **sem
  habilitar automaticamente**.
