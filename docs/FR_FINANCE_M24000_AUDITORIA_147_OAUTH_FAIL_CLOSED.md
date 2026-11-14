# M24000 — Auditoria executável das 147 cláusulas e segurança OAuth

**Produto exclusivo:** FR Finance AI Studio, branch de desenvolvimento \`atualizacao-ai-studio-9b46a63187\`, PR #2 DRAFT. **Não misturar** com a frente original FRcaixinha 2.2, ambientes, bancos, backup ou credenciais. **Nenhuma VM OCI, recurso pago ou transação real** faz parte deste pacote.

## Resultado do checkpoint histórico

Fonte: \`docs/CHECKPOINT_CONTRATO_2026-11-01.md\`, transcrição das 147 cláusulas a partir do Contrato Técnico (PDF 38 páginas) e Caderno Mestre (PDF 57 páginas). Integridade dos PDFs é comprovada pelo teste já existente \`backend/scripts/aistudio_contract_clause_extract_ci.py\`.

| Classificação em 01/11 | Contagem | Reinterpretação em M24000 |
|---|---:|---|
| PARCIAL | 58 | Reauditar; nenhum status alterado |
| BLOQUEADO | 50 | Abrir/atualizar evidência de engenharia, provedor ou proprietário |
| NÃO VERIFICADO | 34 | Cada cláusula tem ação de conferência específica, sem conclusão presumida |
| DIVERGENTE | 5 | Exige decisão contratual rastreada, sem alteração silenciosa |
| CONCLUÍDO INTEGRALMENTE | 0 | Mantido por falta de prova integral AT-01 a AT-50 |

**Importante:** essa contagem é histórica. Não significa que 50 fluxos estejam atualmente sem código nem que 34 funcionalidades não existam. Em 06/11 já existem implementações e CI posteriores. O registro \`docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json\` preserva a classificação de origem e adiciona por cláusula: frente responsável, próxima ação, evidência exigida, referência textual anterior e estado de reauditoria. **Nenhuma linha foi promovida automaticamente a CONCLUÍDA.**

## Entregas auditáveis do pacote

1. \`backend/scripts/aistudio_contract_gap_audit.py\` — inspeciona apenas o checkpoint e o JSON versionados. Garante 147 IDs, contagens 58/50/34/5, 84 pendências prioritárias, 0 liberações automáticas e bloqueio de produção. \`--json\` imprime resumo; \`--priority\` mostra todas as 84 ações. Não abre rede, banco, CLI OCI ou solicita senha.
2. \`backend/tests/test_m24000_contract_gap_147_ci.py\` — confirma fidelidade entre texto e registro e 34 ações individualizadas, sem inventar conformidade.
3. \`backend/app/mp_oauth_staging_token_sink.py\` — correção de segurança na compensação de falhas. Depois de tentar registrar a revisão PENDING, o backend só pode chamar \`store.cancel\` quando o registro atomizado foi comprovadamente convertido de PENDING para FAILED. Caso o retorno da criação/ativação seja ambíguo e não exista prova de FAILED, a referência protegida é mantida para reconciliação; **não é apagada por engano**.
4. \`backend/tests/test_m24000_oauth_ambiguous_ack_ci.py\` — testes sintéticos de sucesso, rejeição, revogação, perda de ACK após PENDING e após ACTIVE, preservação de revisão ativa, falha em compensação e segredo não exposto.
5. Regressões atualizadas dos M23500/M23800 para refletir o contrato de segurança correto; os testes antigos assumiam incorretamente que um retorno \`False\` sempre comprovava rollback.

## Próximas tarefas técnicas

**P0, independentes de OCI:** concluir revisão cláusula a cláusula com evidência atual de código, teste e fluxos AT-01 a AT-50; implementar emissão legítima e revogação do consentimento, writer de credenciais realmente criptografado, reconciliação de blobs órfãos, testes de concorrência e falhas de rede; auditar autenticação e recuperação de conta, convite e consentimento persistente; testes integrados de Price, inadimplência, crédito, conciliação de contribuições e rateio anual. Tudo inicialmente com perfis, caixinhas e transações **fictícias**.

**P0, exigem etapas externas/autorizações:** servidor OCI homologação com HTTPS, roles, Vault/KMS/segurança e backup/restauração; autorização da aplicação Mercado Pago Connect e integração comercial Money Out; endpoints reais, webhooks validados, conciliação bancária independente; parecer jurídico/tributário e decisões documentais divergentes. **Não são liberados por testes unitários ou CI.**

**Para executar no Termux, fora do Debian e sem senha:**

\`\`\`bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
python3 backend/scripts/aistudio_contract_gap_audit.py --priority
PYTHONPATH=backend python3 -m pytest -q \
 backend/tests/test_m24000_contract_gap_147_ci.py \
 backend/tests/test_m24000_oauth_ambiguous_ack_ci.py \
 backend/tests/test_m23500_oauth_tenant_token_sink_ci.py \
 backend/tests/test_m23800_oauth_pending_registration_ci.py
git rev-parse --short HEAD
git status --short
\`\`\`

**Governança de liberação:** sem merge da PR #2; PostgreSQL local exclusivo \`127.0.0.1:5433/frcaixinha_aistudio_dev\` intocado; staging SQL apenas no CI isolado; contas dos tenants separadas do caixa da plataforma; Pix IN/OUT, autorização de empréstimos e fechamento com dinheiro real **desativados**.
