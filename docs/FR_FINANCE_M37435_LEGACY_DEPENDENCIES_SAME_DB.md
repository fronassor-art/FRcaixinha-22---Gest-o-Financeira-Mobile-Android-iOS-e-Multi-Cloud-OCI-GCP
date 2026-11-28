# FR Finance M37435 — auditoria de dependencias do valor antigo no mesmo banco

O M37434 foi homologado no Termux (19 testes, mesmo banco). Os registros legados de desenvolvimento continuam presentes: uma politica abaixo do piso, uma cota, doze contribuicoes e uma auditoria protegida. Nao ha pagamentos, Pix, ledger nem emprestimos constatados.

Esta auditoria usa exclusivamente SELECT no banco existente frcaixinha_aistudio_dev (PostgreSQL 18 porta 5433). Analisa tabelas com dependencias FK das quatro familias de registros antigos e conta referencias a esses registros. Confirma tambem que existem dois gatilhos de auditoria imutavel. Nao lista contas, tenant IDs, CPF, sessao, token, credenciais nem registros financeiros individuais.

A ausencia de FKs diretas NAO comprova ausencia de relacoes indiretas e nao autoriza exclusao. O saneamento dos dados exclusivamente sinteticos requer uma futura migracao transacional no MESMO banco, com validacao CI completa, backup restauravel ja concluido, autorizacao explicita e controles de auditoria. Nao desabilitar triggers. Nao importar dados de teste para producao.

Execucao apos CI aprovado: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend python backend/scripts/aistudio_dev_legacy_dependencies_readonly.py

Nenhum banco adicional, limpeza, alteracao financeira ou ativacao real e realizado neste pacote.
