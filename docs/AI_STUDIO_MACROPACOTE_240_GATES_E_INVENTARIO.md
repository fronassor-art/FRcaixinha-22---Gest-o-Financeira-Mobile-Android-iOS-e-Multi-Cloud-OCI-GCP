# FRcaixinha AI Studio — Macropacote 240: gates operacionais sem escrita
Data da preparação: 03/11/2026. Projeto **AI Studio Mobile**, separado do FRcaixinha 2.2.

## Baseline de liberação
- Base: `d76baf6b5aed88b295ecd7c3323099c578e24474`.
- APK 205: oito verificações Android PASS informadas pelo operador.
- Macropacote 220: GitHub Actions #205 6/6 PASS, sincronização ff-only e
  checkpoint somente leitura local PASS; PostgreSQL 5433 e FastAPI ready responderam.
- PR #2 Draft, sem merge; `main` intacta; sem migração local.
- **Não** confundir HTTP ready com auditoria de roles, RLS ou restauração de backup.

## Entregas e gates do Macropacote 240
| ID | Controles e resultados exigidos | Fonte |
|---|---|---|
| 240-01 | Preservar branch, SHA e PR Draft | GitHub |
| 240-02 | Validar sintaxe do script de roles, sem execução local automática | CI shell |
| 240-03 | Validar cluster AI Studio 18, porta 5433 e caminho exclusivo | script local |
| 240-04 | Conferir logins técnicos sem SUPERUSER/BYPASSRLS | script local |
| 240-05 | Conferir membros de roles app/auth e segregação verifier | script local |
| 240-06 | Conferir RLS em tabelas centrais, FORCE RLS em users | script local |
| 240-07 | Verificar ausência de acesso direto a CPF, email, hashes, sessions | script local |
| 240-08 | Limitar o diagnóstico a transações READ ONLY e metadados | shell + CI |
| 240-09 | Validar arquivo .age regular, sem symlink e sem projeto legado | shell + CI |
| 240-10 | Conferir SHA-256 fornecido pelo operador | shell + CI |
| 240-11 | Não confundir cabeçalho age e SHA com recuperação válida | saída NOT_TESTED |
| 240-12 | Modelo de checklist de fechamento sem autorização financeira | Python puro |
| 240-13 | Checklist incompleto/adulterado falha fechado | pytest |
| 240-14 | Mesmo com todos os oito sinalizadores, fechamento nunca é aprovado | pytest |
| 240-15 | Persistir bloqueios de POST fechamento real e auditoria manual | pytest |
| 240-16 | Regressão de API, frontend, PostgreSQL/RLS e build Android | CI 6/6 |
| 240-17 | Sincronização local ff-only e verificação de roles no Termux | PENDENTE operador |
| 240-18 | Hash de backup operacional em leitura e guarda da evidência | PENDENTE operador |
| 240-19 | Exercício de restauração operacional em banco descartável segregado | PENDENTE autorização/infra |
| 240-20 | Homologação física do APK do pacote | PENDENTE operador |

**Aprovação:** CI PASS permite criar APK para teste, mas não atesta roles
locais, nem backup operacional, nem reconciliação, nem fechamento definitivo.

## Termux: diagnóstico da conta técnica — somente leitura
Após `git merge --ff-only` até o commit alvo exato:
```bash
cd "$HOME/frcaixinha-aistudio-mobile"
bash backend/scripts/aistudio_240_roles_readonly.sh SHA_COMPLETO_PUBLICADO
```
O `psql -W` solicitará **senha de forma oculta**. Não colar senhas no chat
nem na linha de comando. Faz apenas SELECT em metadados, em BEGIN READ ONLY,
usando default_transaction_read_only e timeout. Retorna BLOCKED se um controle
falhar. Não cria/verifica senhas, nem altera identidades ou dados.

## Arquivo de backup — somente leitura
É necessário ter um backup **já produzido** exclusivamente para AI Studio
e um SHA-256 obtido de fonte independente:
```bash
bash backend/scripts/aistudio_240_backup_integrity_readonly.sh \
    "/caminho/backup_aistudio.age" "SHA256_ESPERADO"
```
Se não existir backup ou SHA conhecido, reportar PENDENTE sem gerar outro.
O script só confere cabeçalho e hash; **não** prova senha/chave correta,
restauração, consistência lógica ou recuperação de um incidente.
Não usar backups do repositório independente.

## Modelo sintético de fechamento anual
`app.closing_readiness_preview.evaluate_closing_readiness_synthetic()` valida
o formato de oito flags artificiais e retorna sempre
`SIMULATION_ONLY_NOT_AUTHORIZED`, `bank_reconciled=False`,
`financial_closing_authorized=False`, `cycle_liquidated=False`.
Mesmo todos True são apenas marcadores fornecidos por entrada e não evidências
auditadas. Sem inserções, comandos SQL, Pix, envio a gateway ou assinatura.

## Pendências que permanecem registradas
| Domínio | Pendente para aprovação futura |
|---|---|
| Banco local | Teste de acesso real com roles app/auth/verifier, RLS com dados sintéticos, migrações apenas autorizadas |
| Backup | Criação exclusiva do AI Studio com guarda segura de chaves, recuperação real isolada e RPO/RTO |
| Auditoria | Identidade de eventos, evidência verificável, hash chain/assinatura, retenção e integridade append-only |
| Contabilidade | Reconciliação real, contas transitórias, completude da trilha e período de competência |
| Fechamento | Fonte do resultado, capital-dias, inadimplência, capital, taxa 15/85, resíduo e conciliação |
| Crédito | Contratos, simulação, elegibilidade, autoempréstimo, aprovações, quitação e crédito externo |
| Pagamentos | Pix, MP multiempresa, webhooks idempotentes, estornos e conciliação por banco |
| Autenticação | Convite, e-mail verificado, recuperação, sessões e histórico de acesso |
| SaaS | Planos, cobrança, licenças, suspensões e reembolsos |
| LGPD | Permissões, minimização, exportação/eliminação e retenção |
| OCI/GCP | Segredos, TLS, monitoramento, deploy, custos e política de backups |
| AI Studio | Comparação posterior com código GitHub/Termux, sem upload agora |
| Android | Build, atualização de assinatura, offline, performance e homologação |
| Governança | PR #2 Draft, revisão independente, não misturar FRcaixinha 2.2 |

Não marcar PENDENTE como PASS por inferência e ampliar o inventário se novos
problemas forem identificados. Não implantar em produção nem liberar dinheiro real.
