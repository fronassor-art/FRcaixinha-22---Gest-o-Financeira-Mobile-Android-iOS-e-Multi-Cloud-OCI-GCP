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
