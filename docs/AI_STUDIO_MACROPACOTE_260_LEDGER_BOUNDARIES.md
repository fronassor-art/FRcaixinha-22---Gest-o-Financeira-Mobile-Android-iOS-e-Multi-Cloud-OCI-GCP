# FRcaixinha AI Studio — Macropacote 260: leitura contábil limitada

Este pacote é exclusivo do **AI Studio Mobile**, separado do projeto FRcaixinha 2.2. Sem migração, escrita no PostgreSQL operacional, pagamentos, fechamento ou alteração de identidades.

## Baseline confirmado
- Base GitHub: `fc27e4cf69947000282f3344bb3babb07d1a9075`.
- APK #207: 7/7 verificações físicas **informadas pelo operador** em 03/11/2026; não constituem prova independente de integridade de todos os registros.
- CI #207: 6/6 PASS; Termux ff-only PASS; PR #2 Draft, sem merge.
- Backup AI Studio criptografado: SHA-256 e leitura do catálogo PASS; restauração isolada de PostgreSQL 18, teste de estrutura e limpeza PASS, relatados pelo operador.
- Não inferir backup fora do celular, RPO/RTO, auditoria contábil independente, reconciliação bancária ou ambiente de produção.

## Entrega 260: consultas sem paginação permanecem limitadas
- `/accounts`: máximo 500 contas, consulta até 501 e falha HTTP 503 se exceder. Nunca apresentar amostra como totalidade.
- `/transactions`: máximo 500 transações, ordenação estável e falha HTTP 503 se exceder, antes de buscar seus lançamentos.
- Detalhes de cada transação: máximo 100 contrapartidas; limite SQL 101, erro HTTP 503 se exceder.
- JOIN do detalhe inclui `a.tenant_id = e.tenant_id`.
- Apenas SELECT e autorização de administrador do próprio tenant; Master e Membro seguem negados.
- CI verifica limites, fail-closed, tenant, ausência de escrita e regressão de toda a aplicação.

## Pendências preservadas
1. **Backup fora do celular** e chave privada `age` sob guarda independente; comprovação segura, sem publicar segredos.
2. **Recuperação operacional completa**: RPO/RTO, contagem de linhas, integridade referencial, operações em ambiente reconstruído, sem afetar banco real.
3. **Livro-Razão completo**: paginação autorizada, extrato por conta, competência, filtros, trilha imutável e reconciliação; os limites 500/100 são controles temporários, não solução de escala.
4. **Banco local**: autenticação real com roles app/auth/verifier e teste de políticas RLS entre tenants com dados sintéticos e aprovação específica.
5. **Auditoria**: origem verificável, append-only, retenção e cadeia de hashes/assinatura.
6. **Fechamento**: origem de saldos, capital-dias, inadimplência, taxas 15/85, resíduos, conciliação e dupla aprovação; **não habilitado**.
7. **Crédito**: contratos, elegibilidade, aprovações, empréstimos internos/externos, quitação e integração com políticas legais.
8. **Pix/Mercado Pago**: instituições por empresa, webhook idempotente, estornos, conciliação e testagem; **sem dinheiro real**.
9. **Master/SaaS**: papéis, onboarding, planos, licenças, suspensão e governança.
10. **LGPD**: minimização, consentimento, exportação/eliminação, retenção e trilha.
11. **OCI/GCP**: TLS, segredos, deploy, custos, monitoramento e backups externos.
12. **Android**: assinatura, offline, performance e homologação física específica do APK resultante.
13. **AI Studio**: comparar futuramente com GitHub/Termux; nenhum upload ou edição agora.
14. **Governança**: PR #2 Draft, revisão independente, `main` intocada, não confundir CI com autorização financeira.

## Critério de continuidade
Exigir CI 6/6 PASS, FF-only no Termux e homologação Android específica da versão. Falha ou resposta acima dos limites retorna indisponibilidade clara, sem dados parciais nem operações reais.
