# FR Finance AI Studio — Supermacropacote M28700–M29000

**Escopo:** projeto FR Finance AI Studio apenas; repositório e branch
`atualizacao-ai-studio-9b46a63187`, PR #2 DRAFT. Não misturar com FRcaixinha
2.2 independente. Não alterar o M28619 no Termux, M28621 no GitHub ou
o PostgreSQL local 18 porta 5433. Nenhum serviço financeiro real é ativado.

## M28700 — mapa explícito de liberação, sem falsas aprovações

O módulo `backend/app/release_evidence_matrix.py` integra **20 requisitos
de lançamento** existentes em `launch_readiness.py` com os **7 gates
externos** existentes em `operator_release_worklist.py`. Total:
27 **categorias de prova** (não são 27 funcionalidades novas).

Para cada requisito, informa fonte de engenharia presente/ausente, prova
de aceitação exigida e status **não homologado em staging**. A presença
de código, teste CI verde, certificado local ou VM criada **não equivale**
a homologação funcional, identidade ou movimentação financeira autorizada.

Os 147 itens de `FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json`
são preservados como **baseline histórico**, com 58 parciais,
50 bloqueados, 34 não verificados e 5 divergentes. Não é avaliação
atualizada da conformidade contratual. Nenhum item é promovido a PASS
por este pacote.

## M28800 — roteiro prioritário por dependência

1. **Identidade:** autenticação de produção, MFA Master, aprovação independente,
   isolamento RLS de dois tenants e sessões revogáveis.
2. **Primeiro acesso:** convite durável, e-mail verificado, texto jurídico
   canônico, aceite pelo próprio destinatário, recuperação de senha.
3. **Infraestrutura:** VM OCI, HTTPS e DNS, recuperação de backup,
   migrações/roles e SHA runtime vinculado ao APK release.
4. **Dinheiro:** OAuth Connect por administrador, Orders Pix com conciliação,
   autorização comercial para saída, contabilidade de três fontes,
   fechamento anual com inadimplência e saída voluntária.

Cada linha possui o identificador da **prova de aceitação em staging**.
Nenhuma prova de staging é dada como concluída neste ponto.

## M28900 — regressões executáveis

`backend/tests/test_m28700_m29000_release_matrix_ci.py` testa:

- todos os 20 gates técnicos e 7 de provedores permanecem bloqueados;
- uma entrada pública de OCI válida nunca autoriza Pix ou usuário;
- input inválido para HTTPS, região ou webhook é recusado;
- histórico das 147 cláusulas é imutável em termos de autorização;
- cenário Master aparentemente válido continua sem criar convite;
- autoaprovação, replay e conflito de revisão não são admitidos;
- rateio hipotético preserva 15% administrador / 85% membros;
- ausência de membros mantém pool não distribuído, sem pagamento;
- CLI não imprime credenciais nem toca em banco/OCI/MP.

O workflow `.github/workflows/validacao-atualizacao.yml`
passa a executar esses testes na PR. **PASS da CI prova somente
a regressão sintética correspondente**, nunca a implantação real.

## M29000 — comando local seguro no Termux (APÓS CI PASS)

Este procedimento lê somente o manifesto público protegido que já fica
em `$HOME/.config/frfinance-aistudio/provider-public-inputs.json`, se
existir. Não exibe valores nem credenciais.

```bash
cd "$HOME/fr-finance"
git status --short
git fetch origin atualizacao-ai-studio-9b46a63187
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 backend/scripts/aistudio_release_evidence_matrix.py audit
PYTHONPATH=backend python3 backend/scripts/aistudio_release_evidence_matrix.py plan
PYTHONPATH=backend python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```

Não executar `aistudio_local_migration.sh apply`, não executar SQL de
`ci_migrations` ou `staging_migrations` no Termux, não fazer bootstrap de
contas reais nem configurar `FR_FINANCE_PIX_REAL=true`.

## Fatores externos que ainda bloqueiam a entrega real

A data de entrega e a ativação de pessoas reais dependem de provas
que não podem ser produzidas por um commit ou um teste sintético:

- A1 OCI provisionada, SSH, isolamento, HTTPS, banco, backup-restauração.
- MFA Master e processo de aprovação de contas operacionais implantados.
- Fluxo real de convite, confirmação de e-mail, consentimento e revogação
  com concorrência no PostgreSQL de staging.
- Assinatura e atualização de APK release testada no telefone.
- Mercado Pago Connect e Pix de entrada homologados por tenant.
- Pix de saída depende ainda da habilitação específica do provedor.
- Todas as regras financeiras e contratuais precisam de cenários fim a fim,
  auditoria e aceite formal antes de dinheiro real ou contas reais.

O status real é `PRODUCTION_NOT_AUTHORIZED`. **Este pacote acelera
o diagnóstico e as provas, não desbloqueia artificialmente riscos.**

## Próximos macropacotes planejados

- **M29100–M29400:** segurança de cadastro e testes adversariais da cadeia
  Master → Administrador → Membro, com evidências de transação durável.
- **M29500–M29800:** provas de integridade contábil, fechamento,
  inadimplência e saída voluntária entre dois tenants.
- **M29900–M30200:** runbooks de staging OCI agnósticos de provedor,
  backup/restore, certificação HTTPS e entrega Android.
- **M30300–M30600:** Mercado Pago/SMTP em staging com provedores testados
  apenas sob autorização explícita de rede e ambientes próprios.

Nenhum desses pacotes futuros é considerado executado por este documento.
