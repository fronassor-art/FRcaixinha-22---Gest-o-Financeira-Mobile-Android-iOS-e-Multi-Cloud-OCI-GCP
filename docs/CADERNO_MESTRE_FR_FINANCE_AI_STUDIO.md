# Caderno Mestre — FR Finance AI Studio

**Produto:** FR Finance — gestão e controle financeiro.
**Frente exclusiva:** aplicação React/TypeScript + Capacitor e backend FastAPI desenvolvidos no Google AI Studio, sem compartilhamento de banco, código, operação ou credenciais com o **FR Caixinha 2.2 independente**.
**Estado deste documento:** consolidação técnica de regras e decisões encontradas no repositório em 09/11/2026; não equivale a assinatura de contrato jurídico ou revalidação automática de cada cláusula histórica.

## 1. Identidade e governança
- Marca visível em todas as interfaces, metadados, backend, documentos de uso corrente e materiais comerciais: **FR Finance**.
- Diretório canônico da instalação de desenvolvimento no Termux: `$HOME/fr-finance`. Repositório GitHub e branch continuam com os identificadores originais por compatibilidade até eventual migração do endereço remoto formalmente controlada.
- Administrador Master gerencia plataforma, planos, assinaturas e suporte técnico. O Master não obtém por essa condição acesso livre à contabilidade das caixinhas.
- Cada Administrador opera sua própria caixinha e seus vínculos. Cada Membro acessa somente o seu contexto e os recursos permitidos; mesmos indivíduos podem ter vínculos em mais de uma caixinha sem compartilhamento financeiro.
- Uma caixinha é uma unidade de controle financeiro, não uma marca nem uma instituição bancária.

## 2. Receitas, cotas, capital, crédito e rateio
- **Caixa Master da plataforma:** receitas de planos e assinaturas de administradores, sem mistura com capital dos membros.
- **Caixa de cada caixinha:** entradas, saídas, custos, crédito e patrimônio segregados por tenant, com autorizações e conciliação próprias.
- O cálculo anual *previsto para homologação* distribui **15% do lucro líquido real elegível** ao administrador da caixinha e **85%** aos membros elegíveis proporcionalmente ao Capital-Dias; a soma dos centavos deve fechar exatamente.
- Capital aportado, principal de empréstimo e mera aprovação de Pix não são lucro realizado. Sem conciliação e prova contratual, os valores ficam em revisão e nenhuma transferência é feita.
- As cotas e seus valores obedecem à política e à versão do ciclo da caixinha, com verificações de piso e competência no backend. Não alterar preços retroativamente.
- Regra definitiva: o administrador escolhe explicitamente o valor por cota no início de cada ciclo, mínimo R$ 150,00 (não valor universal fixo), sem preenchimento automático.
- Correção exclusivamente no projeto, repositório, diretório Termux e banco PostgreSQL 18 frcaixinha_aistudio_dev já existentes. Não clonar nem trocar bancos. GitHub/CI integral primeiro, depois fast-forward no Termux, auditoria e migração controlada somente na base atual com autorização específica, preservando backup e trilhas de auditoria.
- Crédito e amortização Price são funcionalidades sujeitas a regras contratuais, idempotência e segregação; taxas presentes em testes são exemplos e não autorizam oferta real.

## 3. Inadimplência, saída e fechamento
- Distinguir **90 dias de atraso** de **três competências consecutivas não quitadas**: são fatos diferentes e não se substituem automaticamente.
- Restrições de rateio, multas e juros dependem de contrato específico, prova de conciliação e revisão jurídica. Não confiscar automaticamente capital.
- Saída voluntária conserva direitos e obrigações; registrar solicitação, versão contratual, auditoria e conciliação da restituição antes de qualquer encerramento.
- Fechamento anual requer evidências de receita realizada, despesas, perdas, ajustes, elegibilidade, direitos de saída, ausência de pendências de conciliação e aceites exigidos. O demonstrador não executa liquidação.

## 4. Adesão e identidade
- Cadastro individual por convite: Master → Administrador; Administrador da caixinha → Membro.
- Exigir identidade e sessão verificadas, segregação de papéis e tenants, contrato canônico versionado, aceite expresso do destinatário, verificação real de e-mail e revogação de sessões em recuperação de senha.
- A plataforma não libera contas reais enquanto MFA Master, aprovação independente, outbox/SMTP, PostgreSQL RLS, provedores e auditoria transacional não forem homologados.

## 5. Infraestrutura e liberação
- Desenvolvimento e testes usam GitHub Actions, PostgreSQL descartável e Termux. O banco AI Studio exclusivo no Termux permanece `127.0.0.1:5433/frcaixinha_aistudio_dev` por compatibilidade.
- OCI São Paulo é infraestrutura planejada; máquina virtual, HTTPS público, backup/restauração e monitoramento requerem evidência operacional antes da produção.
- Mercado Pago Connect e Pix Orders/entrada/saída exigem autorização e testes independentes por tenant. Pix de saída também depende de habilitação comercial do provedor.
- Operações com dinheiro real, rifas e cadastros reais estão desativados; nenhum teste offline promove automaticamente uma funcionalidade a produção.

## 6. Linhagem documental e controle de alterações
- **Fonte própria técnica atual:** [Contrato Técnico Mestre — FR Finance AI Studio](CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md).
- **Inventário histórico:** [registro de 147 cláusulas](FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json) e [checkpoint histórico de 01/11/2026](CHECKPOINT_CONTRATO_2026-11-01.md).
- Os dois PDFs em `public/assets/aistudio/` intitulados FRcaixinha 2.2 são **referências históricas de origem**, não Caderno/Contrato atual do FR Finance. Mantê-los byte-idênticos e com nomes originais garante rastreabilidade.
- As 147 cláusulas legadas são registro de pendências e conflitos, **não** 147 disposições automaticamente aprovadas para esta nova frente. Exige-se decisão por cláusula, revisão jurídica quando aplicável e prova de aceitação.
- Documento sujeito a atualização versionada na branch AI Studio. Não faz merge à `main`, não aplica SQL e não ativa usuários ou pagamentos.

**Prontidão de produção: NÃO AUTORIZADA.**

## 7. Crédito Especial/Extraordinário e Comunicação Multicanal — CM-CRED-EX-01 (implantação controlada)
- **CM-EX-01 a 03:** autorização individual/seleção múltipla, teto excepcional específico, validade e justificativa por membro, ciclo e tenant; análise de risco e política vigente permanecem exigidas.
- **CM-EX-04 a 05:** registrar avaliação reforçada, preparar/publicar/cancelar campanhas auditáveis; resposta individual, sem autoempréstimo ou pré-aprovação financeira.
- **CM-EX-06 a 08:** push prioritário, inbox interna, e-mail, WhatsApp e SMS independentes; interesse, recusa, simulação Price e preferências de marketing sem disparos reais.
- **CM-EX-09 a 11:** revalidar limite, ciclo, adesão, contrato e liquidez; impedir vazamento entre tenants e alteração de ledger/reserva/Pix por campanha.
- **CM-EX-12:** testes de CI, migration candidata RLS em PostgreSQL descartável e APK debug físico; **sem** alegar homologação de transporte externo antes de provas.
- **Entradas de engenharia:** `backend/app/special_credit_contract.py`, `backend/app/special_credit_channels.py`, `backend/app/routers/special_credit.py`, `src/components/SpecialCreditView.tsx` e `backend/migrations/110_fr_finance_special_credit_offline.sql`. SQL está apenas versionado, não aplicado ao banco original.
- **Configuração sandbox:** `FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES` exige `FRCAIXINHA_TEST_AUTH=1` e ambiente não produtivo; nunca ativar em produção por CI. Push Android nativo/FCM, Brevo, WhatsApp Business e SMS reais requerem integração, credenciais, permissões e autorização operacional separadas.
- **Matriz detalhada:** [FR_FINANCE_CREDITO_ESPECIAL_EXTRAORDINARIO_M39010.md](FR_FINANCE_CREDITO_ESPECIAL_EXTRAORDINARIO_M39010.md). Preservar `$HOME/fr-finance` e PostgreSQL 5433 `frcaixinha_aistudio_dev`; backup/revisão/autorização expressa antes de migrations locais.

## 8. Preços SaaS flexíveis e promoções Master — decisão aprovada em 12/11/2026
- **Comercial:** somente o Administrador Master edita preços **mensais e anuais independentes** das assinaturas Essencial e Intermediário. Não existe piso comercial fixo ou fórmula anual automática. O preço promocional é uma escolha específica da campanha; não modifica retroativamente contratos ou ofertas anteriores.
- **Memória da decisão:** a antiga regra de anuidade correspondente a dez mensalidades e campo anual apenas calculado (AT-25) foi substituída. Essa mudança **não** revoga o mínimo de R$ 150,00 por cota no ciclo de cada caixinha; produtos e caixas são distintos.
- **SQL112:** desativa a expressão gerada obrigatória na coluna `annual_price` preservando os valores históricos, mantém RLS FORCE e autoriza somente inclusão de versões novas pelo MASTER auditado. É candidata à migração local; não presumir aplicada por CI.
- **SQL113:** versões de campanha comerciais `DRAFT`, `PUBLISHED`, `CANCELED` por inserção imutável, separadas por plano, mensal/anual, preço, público, título/benefício, início/fim, versão de referência, motivo e autor Master. Rejeitar sobreposição do mesmo plano/período e alterações concorrentes. Sem canal externo.
- **Elegibilidade técnica inicial:** administrador de tenant ativo, sem licença/preparação SaaS anterior, validado somente no servidor por função com contexto da sessão; listas de ofertas não mostram rascunhos, cancelamentos ou campanhas vencidas. A definição comercial detalhada de “novo administrador” poderá ser refinada sem prometer direitos ou descontos a outras categorias.
- **Divulgação:** somente a seção interna de licenciamento do app. Criar rascunho não publica. Publicar não contrata, não fatura, não ativa licença, não envia e-mail/Brevo, SMS, WhatsApp ou push, e não automatiza desconto em pagamento.
- **Validação de código:** GitHub Actions deve conferir catálogo/hash dos SQL112 e SQL113, contrato de autorização MASTER/TENANT_ADMIN, campo anual editável, filtros de vigência, rejeição de versão obsoleta, histórico de estado, API sem Pix/SMTP, regressão de UI e ausência de preços promocionais fictícios.
- **Migração e homologação:** sincronizar somente o repositório original `~/fr-finance` por fast-forward; inspecionar PostgreSQL 18 original `127.0.0.1:5433/frcaixinha_aistudio_dev`, conservar backup e exigir aprovação interativa distinta antes de aplicar SQL112+SQL113 na mesma transação; revalidar RLS e preservação histórica. Não misturar projeto 2.2, não reaplicar migrations antigas, não ativar produção ou realizar cobranças reais.
- **Plano Ampliado:** permanece bloqueado até teto de membros/cotas e decisão contratual específica. Preços de catálogos antigos são históricos, não piso obrigatório.
- **Próximo gate antes da produção:** congelamento de oferta vinculada à versão de campanha, aceite inequívoco e documentado, consentimentos de comunicação, integração do provedor de cobrança e conciliação. A publicação informativa atual **não** completa esses requisitos.

**Contraparte normativa:** [CTM-SAAS-01 a CTM-SAAS-09](CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md). As fontes históricas PDF e o FR Caixinha 2.2 original não são alterados nesta frente.

## 9. Caixa exclusivo Master e Caixa exclusivo do Administrador — M39090 (consulta segura)
- A plataforma mantém **Caixa Exclusivo do Administrador Master** para evidências de receitas SaaS e assinaturas, sem acesso a capital, saldos ou Livro-Razão de membros das caixinhas.
- Cada caixinha dispõe de **Caixa Exclusivo do seu Administrador Titular** para acompanhar, em caráter documental, a participação prevista de **15% do lucro líquido elegível**; os **85% dos membros** permanecem no cálculo e na conciliação próprios, sem apropriação antecipada.
- Os dois painéis do aplicativo existem na navegação por papel e são exibidos apenas após autenticação; a API revalida o papel e o tenant a cada GET no PostgreSQL RLS.
- A primeira entrega M39090 disponibiliza **indicadores contabilizados e status**, não conta bancária, saldo confirmado, comissão creditada, recebimento, transferência ou saque. Campos de saldo ficam `null`/“Não disponível” até prova independente de conciliação e fechamento.
- Contagens de intenções SaaS não representam receita recebida; contagens de lançamentos da caixinha não representam dinheiro do administrador. Jamais derivar saldo de somatório de intenções, quotas ou campanhas.
- Caminho posterior para operacionalizar saldos: desenho de contas de titularidade, regime de competência, fechamento aprovado, lançamentos imutáveis, conciliação do provedor, trilhas de autorização/auditoria, RLS, migrações revisadas e homologação de provedores. **Não aplicar SQL original nem habilitar Pix real sem autorização expressa adicional.**
- Erro 404 em Campanhas do Crédito Especial deve ser diagnosticado primeiro comparando as rotas do FastAPI realmente em execução com as rotas versionadas; mudança de banco ou reativação de crédito não é solução automática.

## 10. M39910 — Histórico documental dos caixas exclusivos, sem saldos

- O Caixa Master pode visualizar apenas a sequência temporal dos estados de intenções SaaS e preparações de assinatura, limitada a dez itens, nunca tratada como ingresso financeiro comprovado.
- O Administrador titular pode consultar, como **referência coletiva**, eventos temporais do Livro-Razão da própria caixinha, limitados a dez itens; esses registros não são seu histórico de remuneração pessoal.
- Todos os registros permanecem sem valores monetários exibíveis: `amount_cents=null`, `available_balance_cents=null`, `settlement_verified=false` e `transfer_enabled=false`.
- Regra 15%/85% de lucro líquido anual continua normativa. Política de ciclo, reconciliação, elegibilidade e fechamento devem ser provados antes de qualquer reconhecimento, rateio ou transferência; M39910 não realiza apuração.
- GET com autenticação de Master ou Admin titular, RLS, cache desabilitado; 404 do FastAPI antigo não pode inventar histórico ou comprometer os demais painéis.
- Não alterar o PostgreSQL do FR Finance (5433) nem acessar a base independente FR Caixinha 2.2; sem migração, reinício de serviços ou ativação de pagamentos.
- Rastreabilidade técnica: `docs/FR_FINANCE_M39910_HISTORICO_DOCUMENTAL_CAIXAS.md`.

## 11. M39920 — Fundação de escrituração dos três caixas (homologação offline)

- A plataforma distingue três domínios financeiros: `PLATFORM_MASTER` para receitas/despesas de SaaS, `TENANT_ADMIN_OWN` para remuneração própria do administrador titular e `TENANT_COLLECTIVE` para cotas, empréstimos e patrimônio de cada caixinha. Não misturar fundos.
- A futura escrituração exige partidas dobradas DR=CR, contas exclusivamente do próprio domínio/tenant, valores inteiros em centavos, referência rastreável e recusa de lançamentos duplicados ou desbalanceados.
- O pacote M39920 **apenas valida o formato** de candidatos e testa um esquema TEMP com ROLLBACK em PostgreSQL 18 descartável; nenhuma receita, remuneração, despesa, saldo, contabilização ou transferência é criada no banco original.
- O rateio previsto 15%/85% exige política versionada, lucro líquido elegível, Capital-Dias, auditoria, conciliação e autorização de fechamento. Prévia de lançamento não prova pagamento nem receita.
- Migração original, permissão de escrita e pagamentos reais dependem de autorização expressa e novos gates de RLS, contabilização imutável, idempotência e evidência externa; os dois projetos PostgreSQL permanecem isolados.
- Referência técnica: `docs/FR_FINANCE_M39920_ESCRITURACAO_PREPARACAO_CAIXAS.md`.
