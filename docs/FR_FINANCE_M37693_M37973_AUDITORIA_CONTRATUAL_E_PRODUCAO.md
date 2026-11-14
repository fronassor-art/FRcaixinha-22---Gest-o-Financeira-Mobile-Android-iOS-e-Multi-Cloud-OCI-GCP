# FR Finance AI Studio — M37693–M37973 | Auditoria integral para homologação de produção

**Checkpoint de partida confirmado pelo operador:** M37500–M37692, commit 1b1a68c (326 testes offline PASS em Termux), 109 arquivos SQL inventariados, sem migrações locais neste pacote. **Escopo:** FR Finance AI Studio, branch atualizacao-ai-studio-9b46a63187. Não misturar banco/código/credenciais com FR Caixinha 2.2 independente.

## Decisão de lançamento: NÃO, ainda não pronto para produção real

Os testes offline atestam apenas os cenários exercitados. **Vinte gates técnicos reais e sete gates de provedores externos permanecem sem comprovação independente de produção**, assim como a matriz de 147 cláusulas históricas. Não houve no M37693 provisionamento OCI, migração SQL local, autenticação de pessoa real, transação Pix, débito, crédito ou ativação.

## Fontes contratuais, com hierarquia correta

1. Fonte vigente: docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md (**29 itens enumerados em seis seções**).
2. Fonte técnica vigente: docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md (**28 itens em sete seções**).
3. Histórico não homologado: docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json (**147 cláusulas**); PDFs FRcaixinha 2.2 são referências de origem intactas, não autorizações do produto atual.

Fotografia histórica (01/11/2026): **58 parciais, 50 bloqueadas, 34 não verificadas, cinco divergentes**. Nenhuma é promovida automaticamente. Divergências 1.6 (rifa demonstrativa), 1.8 (Flutter vs React/Capacitor), 4.1 (política por tenant), 5.3 (suporte) e 8.2 (parâmetros de crédito).

## Supermacropacote auditável — 281 revisões novas, não 281 funcionalidades entregues

IDs contíguos **M37693–M37973**, produzidos por backend/app/m37693_contract_release_audit.py:

| Categoria | Itens | Evidência necessária |
|---|---:|---|
| Caderno Mestre vigente | 29 | Decisão, implementação, teste e revisão item a item |
| Contrato Técnico vigente | 28 | Arquitetura, migrações, autenticação, release e prova operacional |
| 147 cláusulas históricas | 147 | Revalidação sem herdar aprovação do produto 2.2 |
| Gates técnicos | 20 | Staging operacional e testes E2E independentes |
| Gates externos | 7 | Autorização real de provedores, prestadores e operador |
| AT-01 a AT-50 | 50 | Teste reproduzível e resultado assinado pelo responsável |
| **Total** | **281** | **Todas inicialmente pendentes** |

O plano anterior de **192 tarefas M37501–M37692** continua registrado como planejado, não implementado por esta auditoria. A nova matriz identifica obrigações; não resolve código faltante, não cria VM e não preenche evidências.

## Sequência de execução e critérios de aceite por frente

### P0 — identidade, consentimento e governança
- Autenticação real Master/Admin/Membro, sessões revogáveis, MFA Master e aprovação independente; dois tenants sem leitura, escrita ou elevação cruzada.
- Convites single-use e aceites individuais versionados, texto jurídico canônico SHA-256, e-mail verificado com entrega real em caixa autorizada e recuperação de senha que revoga sessões.
- Revisar divergências contratuais 1.6/1.8/4.1/5.3/8.2; validar taxas, operações de crédito, LGPD, tributação e fronteira regulatória sem supor autorização.

### P0 — OCI, banco e Android
- Confirmar VM de staging realmente RUNNING, DNS/TLS, portas mínimas, IAM/Vault, logs protegidos e infraestrutura; preparar alternativa sem gastos não autorizados.
- Testar backup e restauração de PostgreSQL em ambiente isolado, RLS, roles, catálogo de migrações com SHA, paridade e operação segura; **nunca aplicar staging_migrations/ci_migrations no banco 5433**.
- Ligar API FastAPI ao cliente Android em staging, provar versão implantada e release assinado, testes de atualização física, perdas de rede, notificações e isolamento de perfis.

### P0 — financeiro e provedores
- Cobranças SaaS Master separadas das caixinhas; autorização de cada administrador; Mercado Pago Connect OAuth PKCE/state/refresh e Vault.
- Pix de entrada Orders com webhook assinado, consulta direta ao provedor e conciliação PSP/aplicação/Livro-Razão; idempotência, reversões, estornos e tarifas.
- Pix saída/Money Out somente com **habilitação comercial expressa do provedor**, limites, destinatário verificado, reservas e dupla aprovação.
- Valor mínimo de **R$ 150 por membro/ciclo**, explicitamente definido pelo administrador ao abrir o ciclo; 90 dias de atraso não são necessariamente três competências; saída voluntária sem confisco; lucro líquido elegível 15% administrador/85% membros por Capital-Dias e fechamento exato em centavos.

### P0 — aceitação e decisão
- Executar AT-01–AT-50 no staging apropriado com contas sintéticas autorizadas e dois tenants; auditar cenários adversariais e evidência por cláusula.
- Solicitar revisão jurídica, regulatória, de segurança e operação; registrar GO/NO-GO com responsáveis **sem mecanismo de autoaprovação**.

## Comando offline no Termux, após CI aprovada e sincronização

    cd "$HOME/fr-finance"
    export PYTHONPATH="$PWD/backend" PYTHONDONTWRITEBYTECODE=1
    python -m pytest -q -p no:cacheprovider backend/tests/test_m37693_production_contract_audit_ci.py
    python backend/scripts/aistudio_m37693_contract_release_checkpoint.py summary
    python backend/scripts/aistudio_m37693_contract_release_checkpoint.py checklist
    python backend/scripts/aistudio_m37693_contract_release_checkpoint.py json
    python backend/scripts/aistudio_migration_inventory.py repo-check

**Estado formal:** PRODUCTION_NOT_AUTHORIZED. Pix real OFF; pagamentos reais OFF; ativação real OFF; migrações originais NONE; mutações OCI NONE.

## Regras de progressão

- Documento ou teste presente ≠ homologação real. A matriz distingue fontes, pendências e provas independentes.
- Uma eventual VM RUNNING ≠ HTTPS pronto, autorização jurídica, posse de e-mail, consentimento de membros ou dinheiro autorizado.
- Nenhum usuário ou saldo real deve ser migrado, alterado ou ativado com base nesta auditoria.
- Cada futura mudança que implementa funcionalidade deve trazer teste negativo, teste positivo, isolamento de tenant, prova de CI, sincronização Termux e, quando aplicável, evidência real de staging antes de remover bloqueios.
