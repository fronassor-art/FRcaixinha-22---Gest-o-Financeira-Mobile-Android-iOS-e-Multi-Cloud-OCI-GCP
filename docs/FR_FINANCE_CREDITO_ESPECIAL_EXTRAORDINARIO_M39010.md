# FR Finance AI Studio — CTM-CRED-EX-01 a 06 / CM-CRED-EX-01

**Situação:** implementação autorizada em 11/11/2026, homologação offline primeiro. Nenhuma autorização para usuários, ofertas, marketing, crédito ou Pix reais. **Esta frente é exclusivamente FR Finance AI Studio; não modifica FRcaixinha 2.2.**

## Linhagem contratual
- Origem: Documento Mestre FRcaixinha 1.0 (14/09/2026), cláusula 4.2 — Crédito Especial/Extraordinário.
- Consolidação: Documento Mestre (26/09/2026), cláusula 6.2.
- Minuta de adesão (12/10/2026), cláusula 12.
- Princípios mantidos: exceção formal para limites superiores; análise de risco, liquidez, exposição/concentração, garantia quando cabível, justificativa, aprovação administrativa reforçada, auditoria e limites versionados por ciclo.
- Esta herança é documentação histórica, **não** autorização contratual/jurídica de crédito real. A redação abaixo é uma extensão técnica do FR Finance; preservar a especificidade dos tenants e não copiar regras de outro projeto por presunção.

## CTM-CRED-EX-01 — Autorização individual excepcional
O TENANT_ADMIN autenticado poderá habilitar, para um membro ativo da **mesma caixinha e ciclo aberto**, um teto extraordinário positivo em BRL, justificativa concreta e prazo de vigência. Para vários membros, criar registros individuais, cada qual com teto e expiração próprios. A concessão administrativa é **permissão para solicitar valor excepcional**, não aprovação de empréstimo, não promessa de disponibilidade, não reserva e não movimento de caixa. Não dispensar simulação Price, aceite versionado, verificação de saldo próprio quando exigido, idoneidade, disponibilidade, exposição, limite de ciclo, garantias eventualmente exigidas ou confirmação posterior. É vedado presumir renda. Exige revisão jurídica do modelo de crédito antes de produção.

## CTM-CRED-EX-02 — Campanhas segmentadas
O administrador poderá preparar, publicar, expirar ou cancelar campanha associada a **autorizações especiais individuais**, destinada exclusivamente aos membros autorizados em seu tenant. Cada destinatário terá resposta própria: PENDENTE, INTERESSADO ou RECUSADO. A campanha não altera principal, taxa, prazo, juros, ledger, Pix, elegibilidade para rateio ou status de empréstimo. Revogação impede novas solicitações baseadas no benefício; não desfaz direitos de contratos já constituídos. O valor exibido corresponde a teto para **simulação sujeita à análise**, nunca a crédito liberado.

## CTM-CRED-EX-03 — Comunicação multicanal
Todos os adaptadores serão desenvolvidos no **mesmo pacote**. Prioridade: (1) caixa interna durável e push Android, (2) e-mail via Brevo, (3) WhatsApp Business por API oficial, (4) SMS por provedor configurado. Os **quatro canais externos** exigem gates e homologação **independentes**. Push deve usar transporte Android/FCM homologado; uma simples mensagem na tela não comprova entrega push real. Push negado ou aparelho offline não autorizam disparos repetitivos por outros canais. Links e previews jamais conterão CPF, renda, saldo, dívida, tokens ou valores sensíveis na tela bloqueada.

## CTM-CRED-EX-04 — Consentimento e preferências
Marketing somente mediante preferência granular e base legal demonstrada; opt-out disponível e respeitado. Aviso transacional não é licença para promoção. O banco armazena por tenant/usuário/canal registro explícito do consentimento e suas alterações; ausência de registro equivale a NÃO autorizado. Campanhas direcionadas não expõem identidade/condições de outros membros. WhatsApp: opt-in e modelo aprovado; e-mail: mecanismo de descadastramento; SMS: origem/autorização verificáveis.

## CTM-CRED-EX-05 — Autorização e segurança
Toda API requer sessão autenticada, contexto do tenant e RLS no PostgreSQL. Master não tem acesso a empréstimos/marketing do tenant. A autorização é auditável; publicação e destinatários imutáveis após despacho; idempotência impede duplicação de campanhas e comunicações. Revalidar vínculo e prazo antes da ação do membro. Nenhuma rota criada neste pacote aprova um empréstimo nem ordena Pix. Canal externo OFF mesmo que alguma variável de fornecedor exista; gates independentes precisam de autorização operacional futura.

## CTM-CRED-EX-06 — Homologação
Executar testes de política, fluxo de campanha, não vazamento entre tenants, role MASTER, expiração, consentimento, falha de provedor, idempotência, atualização de UI e ausência de movimentação financeira. CI verde não comprova entregabilidade real. Homologação física Android requer APK com plugin nativo e credenciais push próprias; integração com fornecedores de WhatsApp/SMS requer credenciais, conta e permissão comercial. **Produção e dinheiro real permanecem OFF.**

## CM-CRED-EX-01 — Plano operacional
1. Preservar o branch AI Studio `atualizacao-ai-studio-9b46a63187`; não mudar main, banco ou diretório do Termux.
2. Versionar as cláusulas nos dois documentos mestres, mantendo o histórico de 147 cláusulas como histórico, não como aprovação automática.
3. Criar migração isolada: autorizações, campanhas, destinatários, preferências, outbox e auditoria; RLS FORCE e mínimo privilégio.
4. Desenvolver contrato puro de limite excepcional/expiração e API FastAPI fechada para sandbox.
5. Desenvolver UI administrativa e Minhas Oportunidades com estados reais da API.
6. Especificar/implementar adaptadores separados de push, Brevo e-mail, WhatsApp Business e SMS, sem credenciais nem despachos reais.
7. Validar política Price, pagamentos, contratos, disponibilidade e compliance antes de ligar o crédito extraordinário ao fluxo financeiro real.
8. Rodar testes e CI no SHA publicado; registrar bloqueios externos como BLOQUEADOS, não PASS.
9. Somente após aprovação do CI, apresentar SHA e procedimento de fast-forward para `$HOME/fr-finance` no Termux.
10. Antes de qualquer migração no banco `frcaixinha_aistudio_dev` da porta 5433, exigir backup restaurável, inventário SQL, paridade de schema, funções/roles e **autorização específica**.
11. Gerar/validar APK debug Android e verificar navegação, autorização por membro, publicação, leitura, resposta e canais sem mensagem real.
12. Ativar push, e-mail, WhatsApp, SMS e Pix **somente** em etapas operacionais distintas e explicitamente autorizadas.

### Critérios de saída
- Código e SQL versionados: verificáveis no repositório.
- CI: somente PASS quando workflows aplicáveis do mesmo SHA terminarem com sucesso.
- Envio push/e-mail/WhatsApp/SMS REAL: **NÃO HOMOLOGADO** até prova física e do provedor.
- Autorização de crédito real, migração Termux e Pix real: **NÃO AUTORIZADOS**.
