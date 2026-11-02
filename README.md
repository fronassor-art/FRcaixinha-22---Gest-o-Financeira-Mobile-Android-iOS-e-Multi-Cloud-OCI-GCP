# Aplicativo do AI Studio — desenvolvimento no GitHub

> **Identidade do projeto:** este repositório contém a exportação do aplicativo **Google AI Studio** em desenvolvimento nesta branch. O nome histórico do repositório e alguns identificadores herdados no código mencionam "FRcaixinha 2.2", mas **não autorizam compartilhar dados, infraestrutura, decisões ou alterações com o outro projeto independente de mesmo nome**. Tratar este trabalho como **Projeto AI Studio**.

## Repositório e fluxo oficial

- **Repositório:** `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`
- **Branch de desenvolvimento:** `atualizacao-ai-studio-9b46a63187`
- **PR de integração:** [#2](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/pull/2), mantida **em rascunho** até autorização expressa.
- **Fonte do desenvolvimento:** commits efetuados diretamente no GitHub, acompanhados por GitHub Actions.
- **Termux (Android):** clone local `~/frcaixinha-aistudio-mobile` apenas para sincronização, conferências e homologação especificamente autorizada, via `git fetch` e `git merge --ff-only`.
- **Separação obrigatória:** não usar bancos, clusters, credenciais, backups, repositórios ou decisões técnicas do outro aplicativo.

**Não executar `git branch -M main`, `git push` do Termux, `git reset --hard`, `git clean` ou migrações para realizar a sincronização ordinária.** A branch de trabalho é a da PR #2 e a `main` permanece preservada.

## Situação técnica documentada

O checkpoint de 01/11/2026, publicado antes desta correção do README, registra:

| Verificação | Situação registrada |
|---|---|
| Matriz contratual | 147 cláusulas inventariadas |
| Classificação histórica | 58 parciais; 50 bloqueadas; 34 não verificadas; 5 divergentes |
| Backlog identificado | 37 tarefas: 8 P0, 14 P1, 6 P2, 5 P3, 4 P4 |
| Migrações versionadas | 001–019, ensaiadas em bancos descartáveis no CI |
| Banco exclusivo AI Studio no Termux | PostgreSQL 18.6, `127.0.0.1:5433/frcaixinha_aistudio_dev`, **0 tabelas**, segundo o último relatório do operador |
| CI no checkpoint | 5 verificações aprovadas; isso não constitui aprovação para produção |

**Importante:** as contagens de requisitos representam uma **fotografia documental histórica**, não um índice de conclusão recalculado após cada pacote. Confira evidências por cláusula antes de mudar os estados.

Referências de trabalho:
- [Checkpoint executivo de pendências](docs/CHECKPOINT_EXECUTIVO_PENDENCIAS_AI_STUDIO_2026-11-01.md)
- [Matriz das 147 cláusulas](docs/MATRIZ_147_PENDENCIAS_AI_STUDIO_2026-11-01.md)
- [Integração AI Studio / Termux](docs/AI_STUDIO_MASTER_TERMUX.md)
- [Checkpoint contratual e evidências](docs/CHECKPOINT_CONTRATO_2026-11-01.md)

## Arquitetura e limites

- **Frontend:** React + TypeScript + Capacitor, com compilação Android de depuração no CI. APK compilado não equivale a APK homologado ou publicado.
- **Backend:** FastAPI, PostgreSQL e políticas de isolamento por tenant (RLS) em desenvolvimento e testes.
- **Acesso único:** identidade individual com contextos explícitos `MASTER`, `TENANT_ADMIN` e `TENANT_MEMBER`; não misturar dados de caixinhas.
- **Licenciamento SaaS e Mercado Pago:** partes preparadas/testadas sinteticamente; integração produtiva e conciliação real não liberadas.
- **Pix, desembolso, fechamento financeiro, convites públicos, recuperação por e-mail e operações de bolões/rifas reais:** não liberados para produção. Bolões/rifas permanecem apenas demonstrativos.
- **OCI/GCP e recuperação de desastre:** arquitetura/documentação não comprovam failover produtivo.

## Exemplo matemático de Tabela Price — apenas simulação

Para principal de **R$ 500,00**, taxa **hipotética de 20% a.m.** e **cinco períodos regulares**, o cálculo em `backend/app/routers/loans.py` usa `Decimal`, `ROUND_HALF_UP` e ajusta a última prestação para zerar o saldo:

| Prestação | Valor |
|---|---:|
| 1 a 4 | R$ 167,19 cada |
| 5 (ajuste de centavo) | R$ 167,20 |
| **Total pago** | **R$ 835,96** |
| **Juros totais** | **R$ 335,96** |

O teste `backend/tests/test_price_contract.py` verifica esses valores. Portanto, **não** descrever o caso como cinco prestações exatamente iguais de R$ 167,19. A simulação via API deve usar a **política ativa do ciclo do tenant**, não uma taxa arbitrária informada pelo cliente. O exemplo não autoriza empréstimos reais nem substitui regras de datas do ciclo.

## Como sincronizar com segurança no Termux

No terminal do Android (fora do Debian), primeiro conferir branch e alterações:

```bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git status --short --branch
git branch --show-current
```

Se a branch exibida for `atualizacao-ai-studio-9b46a63187` e o diretório estiver limpo, buscar e aplicar apenas atualização fast-forward:

```bash
git fetch origin
git merge --ff-only origin/atualizacao-ai-studio-9b46a63187
git log -1 --oneline
bash backend/scripts/aistudio_db_local.sh check
```

Se aparecerem divergências, **interromper sem forçar** e investigar. O comando `check` é somente leitura; **não executar `apply`, `verify` ou bootstrap do Master** por causa de uma atualização documental.

## Gates de segurança

Qualquer migração no banco local, provisionamento de contas humanas, cobrança, conexão real com provedor, disparo de convites, instalação de APK, publicação ou merge à `main` exige a autorização específica correspondente. O desenvolvimento na branch e os testes em ambientes descartáveis não equivalem a essas autorizações.

**Fonte de verdade para avanço técnico:** código e commits na branch AI Studio + testes no GitHub Actions + comparação com a matriz contratual + sincronização segura no Termux.
