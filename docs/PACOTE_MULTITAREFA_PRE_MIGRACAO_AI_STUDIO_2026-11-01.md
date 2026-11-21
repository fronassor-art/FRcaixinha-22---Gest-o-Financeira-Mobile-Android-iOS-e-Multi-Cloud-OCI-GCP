# AI Studio — Pacote multitarefa pré-migração 2026-11-01

**Referência:** PR #2, branch `atualizacao-ai-studio-9b46a63187` do repositório
`fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`.

**Regra superior do proprietário:** o banco PostgreSQL 18.6 em
`127.0.0.1:5433/frcaixinha_aistudio_dev` continua **SEM MIGRAÇÃO** e com
**zero tabelas**, conforme a última saída de auditoria do Termux. A PR
permanece em draft e o APK debug não deve ser instalado.

## Objetivo desta entrega

Preparar em um pacote coordenado os mecanismos de adesão e recuperação do
AI Studio, aproveitando a identidade única e a hierarquia
`MASTER → TENANT_ADMIN → TENANT_MEMBER`. Não abrir cadastro público,
não enviar e-mails falsos, não ampliar acesso financeiro do Master.

| Frente | Código | Evidência/limite |
|---|---|---|
| 1. Convites | `014_account_lifecycle_preparation.sql` | Acrescenta revogação, entrega, aceite e referências explícitas |
| 2. Token de uso único | `account_lifecycle.py` | Gera token aleatório, grava somente SHA-256, recusa replay |
| 3. Hierarquia e isolamento | `account_lifecycle.py` | Master prepara convite de administrador; admin ativo de sua caixinha prepara convite de membro; membro não prepara; aceite exige conta existente e e-mail correspondente |
| 4. Recuperação de acesso | `password_reset_tokens` e `account_lifecycle.py` | Token com expiração curta; altera hash Argon2/bcrypt e revoga TODAS as sessões no mesmo commit |
| 5. Testes de abuso e regressão | `test_aistudio_account_lifecycle_ci.py` | Credencial errada, conta distinta, revogação, expiração, replay, ausência de entrega, proteção de token e rollback lógico |
| 6. Transparência de UX | `LoginView.tsx` | Não afirma que enviou e-mail quando o provedor ainda não foi implementado |
| 7. Negação por padrão | `test_aistudio_lifecycle_disabled.py` | Fora do CI isolado, nenhuma função prepara convites/reset; endpoints públicos permanecem em 503 |
| 8. Compatibilidade | GitHub Actions PostgreSQL 16 e 18 | Migrações 001–014 somente em bases descartáveis; PG18 em transação única |

## Fronteira explícita: o que foi PREPARADO, não LIBERADO

O módulo `account_lifecycle.py` contém exclusivamente funções de
**laboratório CI**, protegidas por `FRCAIXINHA_CI_ISOLATED=1` e
verificação do banco `frcaixinha_ci`, porta 5432 e usuário `postgres`.
Não é chamado por endpoints públicos. A simulação de entrega
`simulate_*_delivery_ci` serve apenas para testes; **não representa
confirmação de e-mail real**.

As tabelas `invitations` e `password_reset_tokens` possuem FORCE RLS
sem políticas concedidas aos papéis app/auth. Isso impede leitura ou
gravação de tokens pela API enquanto ainda faltam autorização robusta,
comprovação de titularidade, envio por provedor e rate limit compartilhado.

A conta humana Master e o painel Master SaaS não são duplicados.
Um MASTER não herda direitos financeiros de caixinhas sem vínculo.

## Critérios obrigatórios antes de ativar externamente

1. Provedor de envio de e-mail homologado, com confirmação real de entrega,
   remetente autenticado, domínio validado e links confiáveis.
2. Fluxo público de aceite com verificação do e-mail do destinatário,
   consentimento informado e prova contratual persistente;
   contas novas não surgem diretamente do convite.
3. Revisão das permissões SQL, privilégios das funções `SECURITY DEFINER`,
   bloqueio da API e testes de concorrência e replay por usuários distintos.
4. Rate limit distribuído, tentativa por IP/conta, proteção antiabuso,
   roteamento das respostas para não revelar existência de usuários.
5. Revogação/cancelamento de sessão de maneira transacional e testes de
   mudança de papel durante requisição.
6. Testar regressões com dois tenants, Master, administradores e membros,
   sem dado pessoal real.
7. Auditoria independente antes de habilitar e-mails e dados reais.
8. Autorização expressa do proprietário antes de QUALQUER migração local.

## Restrições permanentes

- **Não executar** `AI_STUDIO_APPLY_MIGRATIONS=YES` no Termux.
- **Não executar** scripts de bootstrap de Master.
- **Não baixar, instalar ou liberar APK** só por PASS no CI.
- **Não ativar** Pix, Mercado Pago real, empréstimos com dinheiro,
  rifas ou bolões. Não misturar banco ou fonte de outro projeto.
- A classificação das 147 cláusulas do checkpoint continua histórica;
  não declarar tudo concluído a partir de testes parciais.


### Compatibilidade com tenant preliminar (Contrato 3.1)

O esquema permite convite de `TENANT_ADMIN` com `tenant_id` ainda nulo
na etapa preliminar de contratação. Para `TENANT_MEMBER`, a caixinha
é obrigatória. A função de laboratório `prepare_invitation_ci` só prepara
convites para tenants existentes; a criação/aceite de administrador **antes**
da criação do tenant continua PENDENTE. Não criar uma caixinha artificial
só para permitir aceite.
