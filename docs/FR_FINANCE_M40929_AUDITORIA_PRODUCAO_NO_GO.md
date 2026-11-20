# FR Finance — M40929: auditoria de produção + identidade de processo Unix (NO-GO)

Data da auditoria: **20/11/2026** (America/Belem). Base conferida antes deste pacote: `1094389d7f593146fde527a3050ebba39be8510b`, branch `atualizacao-ai-studio-9b46a63187`, PR #2 aberta em **Draft**; `main` sem merge da PR. Este documento não representa autorização para produzir efeitos financeiros.

## Evidências realmente observadas

- [CI geral no HEAD-base](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/44770734993): **7/7 jobs success**, abrangendo frontend, API sem banco, PostgreSQL 18 **descartável**, RLS, SQL e APK **debug**.
- [CI M40928](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/44770738457): **2/2 jobs success**, guardião separado por UID em runner Linux efêmero e teste PG18 sintético. O próprio documento M40928 preserva o **NO-GO**.
- Matriz canônica `FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.json`: **330** IDs; **106** requisitos vigentes, **147** itens históricos cuja aplicabilidade precisa ser revalidada, **20** gates técnicos reais, **7** gates de provedores, **50** AT. A matriz registrava **0/20 + 0/7 + 0/50** atestados de forma independente; testes de CI não os aprovam automaticamente.
- Último checkpoint operacional comunicado pelo operador: **M40927 sincronizado somente código-fonte no Termux**, sem migrations, alteração do banco original ou reinícios. O sincronismo M40928/M40929 no aparelho **não está atestado** por esta auditoria.
- Sem acesso neste exame a runtime FastAPI original, PostgreSQL original `:5433`, dispositivo Android, contas OCI/Mercado Pago, segredos, TLS, DNS vivo ou provas de pagamento.

## Laboratório M40929 — prova nova, exclusivamente offline

Um segundo processo não confiável, executado **no mesmo UID do gateway**, consegue conectar-se a um socket Unix sintético em diretório `0700` com arquivo socket `0600`; `SO_PEERCRED` observa o mesmo UID, embora PID seja diferente. Isto comprova que **UID e permissões 0700/0600 não autenticam a identidade de processo ou intenção do chamador**. Não é teste do guardião real M40928, nem demonstra bypass da assinatura Ed25519, do controle de nonce ou do PostgreSQL. O teste exige GitHub Actions isolado, `CI_M40929_OFFLINE=1`, Linux e três flags OFF. Não usa banco, rede, IPC de produção, provedor ou credencial real.

**Efeito sobre arquitetura:** para produção, manter conta de serviço dedicada, ACL restrita do socket, separação de credenciais, atestação e autorização independente de cada pedido, proteção contra reaproveitamento de capacidades, isolamento de host/serviço e monitoramento. Mesmo com essas medidas, a prova documentada de captura de **três** logins SQL + Bearer Master no M40928 continua impedimento **P0** até ser remediada e retestada contra rotas verdadeiras. O protótipo não deve ser promovido à produção.

## Bloqueadores P0 — dependem de implementação + ensaio operacional

| Ordem | Frente | Falta e critério mínimo de liberação |
|---|---|---|
| 1 | SQL e identidade financeira | Remediar GUC falsificável (M40570), emissor SQL legado (M40730), custódia de aprovação Master M40928, owner/superuser, caminhos `SECURITY DEFINER`, ACLs e DSNs reais. Provar isolamento com sessões reais, duas caixinhas e PostgreSQL staging isolado. **Manter M40840 que barra pool financeiro em produção** enquanto não houver desenho independente aprovado. |
| 2 | Infra e runtime | VM/host **realmente disponível e atestado** (OCI A1 sujeito a capacidade ou alternativa aprovada), TLS HTTPS, endpoint de webhook, firewall /32 SSH, IAM mínimo, Vault, backup criptografado, restore testado, logs/alertas e plano de rollback. Verificar PID/commit e ambiente de serviço. |
| 3 | PSP / Mercado Pago | Aprovação de modelo comercial e capacidades do provedor; OAuth Connect com consentimento por administrador, token protegido e rotacionável, autenticação `x-signature` e inbox idempotente, GET autenticado, settlement, estorno/chargeback, reconciliação provedor ↔ sistema ↔ livro-razão, confirmação de permissões Pix de saída se aplicável. Testar primeiro sandbox/contas próprias autorizadas. |
| 4 | Livro-razão e contratos | Evidência de lançamento autoritativo, deduplicação, perdas, taxas, conciliação por transação, reservas, histórico auditável, inadimplência 90 dias, saída, Price/Capital-Dias, cálculo líquido e 15%/85% conforme contratos aprovados; nenhuma baixa financeira por simulação. |
| 5 | Identidade, LGPD e operação | MFA Master, revisão independente de ações críticas, sessão/revogação/rastreio, inventário LGPD, consentimentos, política de retenção, incidentes e resposta, pentest externo, trilhas e responsabilidades. |
| 6 | Android e entrega | Retestar fisicamente a tela inicial após logout/teclado (falha reportada no M40500), três perfis reais, campanhas de crédito/push, ciclo completo e rede intermitente; assinatura **release**, Play/iOS quando aplicável. APK debug não é release. |
| 7 | Jurídico/regulatório e financeiro | Parecer profissional específico sobre propriedade/custódia dos fundos, intermediação, oferta de crédito, distribuição de resultados, tributação, contratos e permissões exigidas. A marca “não é banco” não afasta a necessidade de enquadrar o **fluxo efetivo**. |
| 8 | Aceites | Executar e documentar AT-01 a AT-50 e os 20+7 gates, com responsável, resultado, ambiente, evidência, revisão independente e autorização formal separada. Não promover os 147 itens históricos automaticamente. |

Referências externas para revisão especializada: [BCB Resolução CMN 5.050/2022](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=5050&tipo=RESOLU%C3%87%C3%83O+CMN), [Mercado Pago OAuth](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/additional-content/security/oauth/introduction), [Mercado Pago webhooks](https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-preferences/payment-notifications), [ANPD comunicação de incidentes](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis). O enquadramento BCB é **condicional ao modelo de negócio real**; não há conclusão neste documento de que FR Finance seja SCD, SEP, instituição de pagamento ou dispensado de autorização.

## Continuidade autorizada sem operações reais

1. M40929: teste adversarial local independente de socket Unix + revisão de riscos + CI offline; sem DB, migrations, deploy ou reinício.
2. Próximo pacote: modelo de confiança revisado para autorização de Master **sem credenciais concentradas**, primeiro em revisão de arquitetura e CI descartável. Verificar caminhos GUC/owner/issuer existentes antes de alterar a aplicação.
3. Paralelamente, preparar um inventário de evidências para staging, Mercado Pago e Android; não afirmar gates completos sem comprovação independente.
4. Somente após staging funcional e aprovação jurídica/PSP, planejar migrações controladas com backup, ensaio de restore e rollback; **solicitar nova autorização explícita** antes de alterar PostgreSQL original ou ativar dinheiro real.

**Invariantes:** `PR_2=DRAFT`; `MAIN=NO_MERGE`; `ORIGINAL_PG18_CONNECTIONS=NONE`; `ORIGINAL_PG18_WRITES=NONE`; `MIGRATIONS=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
