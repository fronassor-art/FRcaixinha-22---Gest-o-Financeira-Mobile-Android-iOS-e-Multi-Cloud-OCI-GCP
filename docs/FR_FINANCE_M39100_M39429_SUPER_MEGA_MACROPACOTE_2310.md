# FR Finance — Super Mega Macropacote M39100–M39429

**Data:** 14/11/2026  
**Projeto exclusivo:** FR Finance AI Studio · PR #2 Draft · branch `atualizacao-ai-studio-9b46a63187`  
**Contrato de trabalho:** 330 verificações de origem (106 vigentes + 147 legadas sujeitas a decisão + 20 gates técnicos + 7 gates de provedores + 50 ATs).  
**Volume:** **2.310 tarefas concretas de acompanhamento** = 330 × 7 etapas, com IDs determinísticos `M39100-NNN-SS_FASE`, dependência por etapa, papel responsável e evidência exigida.

> **Status:** macropacote de rastreabilidade, regressão e organização implementado; **2.310 itens planejados não são 2.310 funcionalidades implementadas**. Nenhuma evidência externa ausente se transforma em PASS por CI. Operação real, pagamento, Pix, usuário real e produção continuam bloqueados.

## Entregas de código executadas nesta remessa

1. `backend/app/m39100_full_traceability.py`: valida 330 registros, 106 bullets dos textos originais e anexos, os 147 IDs históricos, os 20 gates e os sete provedores atuais, além de AT-01…AT-50. Confere SHA de blob Git dos seis documentos/fontes congelados e linha/texto exatos dos requisitos vivos. Compara todos os campos com o checkpoint versionado, sem acesso a banco/rede.
2. `backend/scripts/frfinance_m39100_super_macropacote_readonly.py`: modos `audit`, `summary`, `json` e `plan`. `plan` constrói **2.310 registros em JSON** com `task_id`, `check_id`, `requirement_id`, `responsible_role`, `depends_on`, `status=PENDING_EVIDENCE`, `completion_requires` e `production_authorized=false`.
3. `backend/tests/test_m39100_full_traceability_ci.py`: 330 testes parametrizados (um por item) e testes adicionais de desvio/fraude documental: remoção, duplicidade, alteração, desvio de contagem, alteração de SHA, promoção fictícia para `PASS`, rota de arquivo não permitida, mudança de AT e histórico.
4. `backend/tests/test_m39101_android_source_route_ci.py`: comprova pela origem (não por instalação) `com.frcaixinha.app` como applicationId-base, `+.aistudio` como variante debug, assinatura release separada, identidade de três rotas exclusivas e proteção de sandbox do Crédito Especial.
5. Workflow `.github/workflows/frfinance-m39100-supermacropacote-330-ci.yml` e etapa mandatória antecipada no workflow geral `validacao-atualizacao.yml`, executados antes da API e compilação Android.
6. Errata factual `docs/FR_FINANCE_CP20261114_CHECKPOINT_PRODUCAO_NO_GO.md` para DR-03: **não havia incompatibilidade** entre applicationId-base e variante debug. Nenhuma identidade Android, chave ou dados locais foram alterados.

## Sete etapas obrigatórias de cada uma das 330 verificações

| Etapa | Código | Responsável técnico proposto | Condição para passar |
|---|---|---|---|
| 1 | `01_SCOPE` | Jurídico + Produto | Aplicabilidade, redação e versão contratual aprovada, inclusive decisão histórica explícita |
| 2 | `02_CODE` | Engenharia | Código correto, documentação ou exclusão formal justificada |
| 3 | `03_UNIT` | Engenharia/QA | Casos positivos, negativos, retrocompatibilidade e CI |
| 4 | `04_SECURITY` | Segurança | Isolamento Master/Admin/Membro, RLS, concorrência, privacidade e idempotência |
| 5 | `05_E2E` | QA de staging | Fluxo funcional no ambiente correto, evidência reproduzível e dados de teste autorizados |
| 6 | `06_EXTERNAL` | Operação/Provedor/Jurídico | Autorizações e comprovações independentes quando necessárias; não aceitar autorização simulada |
| 7 | `07_SIGNOFF` | Revisor independente | Aceite fundamentado, assinatura e revisão de risco antes de alterar o status da obrigação |

`depends_on` relaciona cada etapa à anterior dentro do mesmo requisito. O requisito não é homologado por execução parcial da sequência. A revisão jurídica poderá concluir explicitamente que uma das 147 cláusulas históricas foi substituída ou não se aplica; isso **não equivale a ignorá-la**.

## Frentes executáveis de engenharia e homologação

| Frente | Escopo e provas obrigatórias | Estado real |
|---|---|---|
| 01. Contrato e versões | 106 itens vigentes rastreados, decisões em 147 históricos e 50 ATs | Auditoria automatizada implantada; decisões e aceites pendentes |
| 02. Android/Capacitor | Build, assinatura debug/release separadas, versão e atualização sem perda | Testes estáticos reforçados; teste físico release pendente |
| 03. API/serviço | FastAPI correto, rotas, assinatura do runtime e health | Registro de rotas testado; 404 pós-reinício ainda depende de teste físico |
| 04. PostgreSQL 18 | Banco original `5433`, role/cluster/DDL RLS e backup/restore | Não mutado por este pacote; auditoria física ainda requerida |
| 05. Identidade | MFA Master, aprovação dupla, autenticação/sessões/isolamento | Regras e CI parciais; produção não atestada |
| 06. Convites/contratos | Convites revogáveis, e-mail verificado, aceite imutável e recuperações | E2E real não atestado |
| 07. SaaS Master | Licença, preço mensal/anual independente, promoção, checkout e estorno | Código de oferta existe; cobrança não atestada |
| 08. Caixa Master | Receitas SaaS, relatórios, despesas, conciliação e extrato | UI de consulta existe; saldo líquido não atestado |
| 09. Caixa do administrador | 15% de lucro apurado, histórico e beneficiário separado | UI de consulta existe; saldo/transferência não atestados |
| 10. Cotas/ciclos | Piso definido pelo administrador, mínimo R$150 e versões de ciclo | CI existe; E2E financeiro ausente |
| 11. Crédito comum | Price, elegibilidade, calendário, até 12/6 conforme política e garantias | Motor simulado; saída real bloqueada |
| 12. Crédito Especial | Campanhas, interesses, recusa, push consentido e canais independentes | Código em sandbox; notificações reais OFF |
| 13. Livro-Razão | Lançamentos, capital, receita, reversão, centavos e concorrência | CI sintética; transações reais não atestadas |
| 14. Mercado Pago OAuth | Connect, autorização por tenant, PKCE/state, Vault e refresh | Provedor externo não homologado |
| 15. Pix entrada | Orders, webhook assinado, idempotência e três fontes | Provedor e conciliação não atestados |
| 16. Pix saída | Money Out autorizado, destino, reservas e antifraude | Permissão comercial externa ainda requerida |
| 17. Fechamento | 90 dias, três competências, saída voluntária, Capital-Dias, 15%/85% | Simulações disponíveis; fechamento real bloqueado |
| 18. OCI/DR | VM, TLS/HTTPS, IAM, Vault, logs, backup/restore e RPO/RTO | Evidências operacionais não atestadas |
| 19. LGPD/segurança | RIPD se aplicável, incidentes, auditoria e pentest | Revisão independente pendente |
| 20. Publicação e aceite | Testes AT-01…AT-50, release Android/iOS, rollback, suporte e GO/NO-GO | NO-GO; nenhum atalho de habilitação |

**Tratamento de dependências externas:** ausência de capacidade A1 Always Free, autorização Money Out, infraestrutura de domínio/HTTPS, aprovação jurídica e testes com dinheiro/pessoas reais não pode ser corrigida apenas adicionando código. O trabalho de engenharia correspondente é rastreável e não se declara aprovado antes da prova.

## Critérios de fechamento do supermacropacote

- Todos os 330 itens rastreados, com fonte e histórico preservados.
- Todo código alterado possui CI e testes negativos.
- Cláusulas novas ou texto alterado sem atualização deliberada do checkpoint causam **CI vermelha** em vez de desaparecer.
- Nenhum `production_verified=true` é aceito pelo checkpoint congelado sem um fluxo separado e revisado de comprovação real.
- O relatório atual permanece `NO_GO_PRODUCTION_NOT_AUTHORIZED`, até aceites assinados e mudança de gate formal.
- Módulos legados FR Caixinha 2.2 não são migrados nem confundidos com a base do FR Finance.

## Próximas execuções seguras

Para inspeção **somente leitura**, quando o HEAD da CI desta remessa estiver sincronizado no diretório original do Termux:

```bash
# Executar no Termux nativo; não reinicia FastAPI ou PostgreSQL.
cd "$HOME/fr-finance"
python3 -B backend/scripts/frfinance_m39100_super_macropacote_readonly.py audit
# Modo de relatório estruturado:
python3 -B backend/scripts/frfinance_m39100_super_macropacote_readonly.py json
# Plano completo: 2310 tarefas em JSON (saída longa):
# python3 -B backend/scripts/frfinance_m39100_super_macropacote_readonly.py plan
```

**Atenção:** não reenviar comandos M39091 já executados. O teste no celular das campanhas segue como evidência operacional pendente, não como justificativa para mexer no banco.

**Segurança:** `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; sem SQL local, sem migração, sem mutação OCI, sem chamadas a provedores. PR #2 permanece rascunho.
