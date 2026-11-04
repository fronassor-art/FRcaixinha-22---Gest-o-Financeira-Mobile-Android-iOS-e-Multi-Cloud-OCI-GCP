# FRcaixinha AI Studio — Macropacote 220: auditoria e rastreabilidade

Projeto exclusivamente **FRcaixinha AI Studio Mobile**, independente do FRcaixinha 2.2.
Baseline: `8247cc1ecf526571a365122b4f74a5a91afdf1e8`; APK 204 homologado
pelo operador (7/7 PASS); GitHub Actions #204 6/6 PASS; Termux sincronizado.
PR #2 deve permanecer Draft; nenhuma migração ou movimentação real autorizada.

## 25 tarefas do Macropacote 220 — execução faseada
| ID | Tarefa | Prova |
|---|---|---|
| 220-01 | Verificar baseline/PR Draft | GitHub |
| 220-02 | Limitar contas ao tenant autorizado | Parser TS |
| 220-03 | Validar valores inteiros de centavos | Parser TS |
| 220-04 | Recusar campos privados/extras | Parser TS |
| 220-05 | Recusar códigos/IDs duplicados | Parser TS |
| 220-06 | Recusar transações de outro tenant | Parser TS |
| 220-07 | Exigir DR e CR equilibrados | Parser TS |
| 220-08 | Rejeitar valor zero, negativo, NaN, Infinity | Parser TS |
| 220-09 | Rejeitar lançamentos e entradas duplicados | Parser TS |
| 220-10 | Rejeitar datas impossíveis, como 30/02 | Parser TS |
| 220-11 | Conferir vínculo de entradas com plano de contas | UI + TS |
| 220-12 | Descartar resposta de sessão/tenant anterior | UI + CI anterior |
| 220-13 | Auditar até 500 eventos sem operação de escrita | FastAPI |
| 220-14 | Responder só com contagens sem PII | API |
| 220-15 | Negar Master/Membro e outro tenant antes do SQL | Python |
| 220-16 | Rejeitar eventos repetidos ou IDs inválidos | Python |
| 220-17 | Ausência de evidência gera revisão, não aprovação | Python |
| 220-18 | NÃO afirmar procedência, imutabilidade ou aprovação | Flags false |
| 220-19 | POST legado de auditoria manual permanece bloqueado | HTTP 503 |
| 220-20 | Rateio matemático continua sem liquidação | Python puro |
| 220-21 | Diagnóstico de Git/FastAPI/PG no Termux só leitura | Script Bash |
| 220-22 | Backup age/restauração descartável | CI existente |
| 220-23 | GitHub Actions 6/6 e APK assinado | PENDENTE CI |
| 220-24 | Sincronização Termux ff-only e diagnóstico local | PENDENTE operador |
| 220-25 | Homologação do novo APK no celular | PENDENTE operador |

**Critério de status:** implementado não é homologado. Qualquer CI FAIL/BLOCKED
impede liberação. Não inventar PASS para controles não testados.

### Termux — script somente leitura
Depois de validar CI e sincronizar o SHA autorizado com merge fast-forward:
```bash
cd "$HOME/frcaixinha-aistudio-mobile"
bash backend/scripts/aistudio_220_termux_readonly_checkpoint.sh "SHA_COMPLETO_VALIDADO"
```
Verifica branch, HEAD, arquivos rastreados, ref remota local, resposta
PostgreSQL 127.0.0.1:5433 e HTTP /api/health e /api/health/ready.
Não imprime senhas, não executa SQL, não restaura backups, não altera banco.
HTTP ready 200 **não** prova conciliação, integridade dos roles ou RLS.

## Registro vivo das pendências — não deixar para trás
| Frente | Pendente | Próximo gate |
|---|---|---|
| Identidade | Entrega externa de convites, reset, cadastro verificado | Backend/serviço + CI e aparelho |
| Sessões | Expiração, revogação, múltiplos papéis e estados de segundo plano | Regressões operacionais |
| Consentimento | Assinatura anual versionada persistente e revogação | Revisão jurídica + auditoria |
| Crédito | Autoempréstimo, pedidos, aprovações, crédito externo e limites | Elegibilidade, consentimento e autorização |
| Tabela Price | Política vigente e casos extremos de amortização | Testes financeiros end-to-end |
| Pagamentos | Pix/MP multiempresa, webhook, idempotência, estornos | Reconciliação bancária independente |
| Contribuições | Baixas, pagamentos parciais e quitação | Banco autoritativo e trilha |
| Ledger | Integridade contábil temporal, saldos e contas transitórias | Conciliação contábil, DR=CR insuficiente |
| Auditoria | Origem autenticada, append-only verificável, retenção | Prova de cadeia e integridade |
| Rateio | Capital-dias, inadimplência, 15/85, resíduos segregados | Dados conciliados e testes jurídicos |
| Fechamento | Apuração e liquidação definitivas | Continuam HTTP 503 |
| Backup | Cópia age com teste de recuperação operacional | Restaurar só em ambiente isolado autorizado |
| PostgreSQL | Roles, RLS e migrações locais | Nenhuma migração sem aprovação específica |
| SaaS Master | Licenças, cobrança, suspensão e reembolso | Banco e gateways confirmados |
| LGPD | Consentimento, exportação, eliminação, retenção | Revisão jurídica, auditoria |
| Cloud | OCI/GCP, TLS, segredos e deploy | Avaliação técnica e custos autorizados |
| AI Studio | Comparar fonte GitHub/Termux com versão no Studio | Não modificar Studio sem autorização |
| Android | Build, assinatura persistente, download, UX, offline | CI + APK físico |
| GitHub | Revisão e merge da PR #2 | Manter Draft e main intacta |

O conjunto acima é o inventário atual, **não uma promessa de exaustividade**.
Reabrir e ampliar sempre que testes encontrarem algo novo. Não criar Master,
não misturar bancos do FRcaixinha 2.2, não liberar dinheiro real.
