# FR Finance

FR Finance é o nome do produto e a única marca pública deste aplicativo. O código ativo, a interface e os documentos vigentes devem apresentar somente essa identidade.

## Repositório e operação

- Repositório remoto já configurado: [FR Finance no GitHub](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP).
- Branch atual: `atualizacao-ai-studio-9b46a63187`; PR #2 permanece em rascunho.
- Diretório nativo do Termux: `$HOME/fr-finance`.
- PostgreSQL original: `127.0.0.1:5433/frcaixinha_aistudio_dev`.
- Identificador Android existente: `com.frcaixinha.app`.

Os identificadores acima permanecem por compatibilidade com o repositório remoto, a sincronização existente, a base já configurada e a atualização do aplicativo instalado. Eles são dados operacionais, não nomes de produto. Esta revisão não renomeia repositório, branch, banco ou pacote Android.

## Documentos vigentes

- [Caderno Mestre FR Finance](docs/FR_Finance_Caderno_Mestre_V2_2_2026-11-24.md)
- [Contrato Técnico Mestre FR Finance](docs/FR_Finance_Contrato_Tecnico_Mestre_V2_2_2026-11-24.md)
- [Checkpoint Termux M40941 de sincronização somente-fonte](docs/FR_FINANCE_M40941_TERMUX_CHECKPOINT_SOURCE_ONLY.md)
- [Bloqueios P0 de produção — issue #5](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/issues/5)

Arquivos de evidência e documentos históricos permanecem preservados para rastreabilidade. Eles não substituem os dois documentos mestres vigentes nem alteram a identidade do produto.

## Estado comprovado em 25/11/2026

O operador confirmou no Termux nativo a sincronização do commit `6e78b270233b299d330a9505dd835b9c20e096f2`. O checkpoint M40941 confirmou a branch fixada, repositório esperado e árvore rastreada limpa. Nenhum banco foi acessado, nenhum SQL foi aplicado, nenhum serviço foi reiniciado e o runtime não foi recarregado ou atestado.

Naquele commit, a CI geral estava em 7/7 e os 148 workflows associados estavam concluídos com sucesso. Isso não aprova produção: a issue #5 continua aberta e `PRODUCTION=BLOCKED`.

## Fluxo seguro

O desenvolvimento segue código e testes na branch autorizada, CI integral no SHA exato e, após validação, um comando de sincronização source-only para o Termux. A sincronização utiliza `backend/scripts/frfinance_m40600_source_sync_only.py`; o checkpoint posterior é somente leitura em `backend/scripts/frfinance_m40941_termux_post_sync_checkpoint_readonly.py`.

A sincronização de fonte não autoriza acesso ou escrita no PostgreSQL, migrations, mudanças de ACL/roles, reinícios ou reload de serviços. Qualquer operação real permanece separada e exige autorização específica.

Flags permanecem `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF` e `PRODUCTION=BLOCKED`.
