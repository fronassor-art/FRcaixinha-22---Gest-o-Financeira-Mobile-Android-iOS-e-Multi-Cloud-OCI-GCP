# FR Finance — M39500–M39599 | Supermacropacote de homologação operacional segura

**Data-base:** 14/11/2026  
**Produto:** FR Finance AI Studio, branch de desenvolvimento \`atualizacao-ai-studio-9b46a63187\`, PR #2 Draft  
**Normas:** Caderno Mestre e Contrato Técnico Mestre vigentes; checklist rastreável de 330 obrigações do CP20261114; macropacote M39100–M39429 de 2.310 etapas.  
**Decisão:** **NO-GO PRODUÇÃO**. Este pacote não aprova produção, não migra, não configura provedor externo e não movimenta dinheiro.

## Finalidade do pacote

Resolver defeitos verificáveis antes dos testes no aparelho e do banco original, sem repetir comandos já apresentados ao operador. O objetivo técnico é impedir dois tipos de falso positivo:

1. **M39091:** o auditor anterior emitia exit code 0 mesmo com \`LOOPBACK_NOT_REACHABLE\`, 404, resposta de outra aplicação ou rota ausente. Isso não atestava as campanhas.
2. **SQL110/111:** o relatório M39032 foi construído quando existiam **53 tabelas públicas**; após a SQL113 ser aplicada, a contagem pode mudar legitimamente. O número global de tabelas não prova que as seis tabelas de crédito estejam seguras.

Nenhum dos dois problemas autoriza mudança no PostgreSQL, abertura de sandbox financeiro, reinício automático ou nova instalação de APK.

## Entrega de engenharia

| Artefato | Verificação executável | Proteção |
|---|---|---|
| \`backend/app/m39500_migration_reconciliation.py\` | Verifica hash Git original de SQL110, 111, 112, 113 e identidade FR Finance; opcionalmente inspeciona os seis objetos de Crédito Especial, 16 políticas, cinco gatilhos, papéis e RLS; reutiliza a conferência integral de SQL112/113. | Só consultas \`SELECT\` no catálogo, dentro de transações \`READ ONLY\`, sem exigir que existam exatamente 53 tabelas. Não declara que a migração foi historicamente executada só por encontrar objetos. |
| \`backend/scripts/frfinance_m39500_readonly_homologation.py\` | Modo padrão \`--offline\` sem credenciais nem banco. Modo opcional \`--original-readonly\` com senha oculta **somente** em terminal interativo, conexão fixada no host/porta/DB/owner/PGDATA esperados. | \`default_transaction_read_only=on\`, timeout e erro sanitizado; nunca conecta à porta 5432 nem instala SQL. |
| \`backend/scripts/frfinance_m39091_api_route_probe_readonly.py\` | Confere as rotas GET de campanhas, crédito e caixas exclusivos no OpenAPI do FastAPI em execução e identidade oficial \`app=FR Finance\` e \`status=ONLINE\` em \`/api/health\`. | Agora retorna exit code **2** quando o processo está ausente, falta rota GET, OpenAPI é inválido ou a identidade é de outro app. Exit 0 exige ambas as provas. Não autentica, não acessa banco, não reinicia serviços. |
| \`backend/tests/test_m39500_migration_reconciliation_ci.py\` | Simulações adversariais de RLS, 5432, PGDATA, papel, privilégio de DELETE, colunas imutáveis, outbox, SQL112/113 e bloqueio de teste não interativo. | Garante prova estática independente do PostgreSQL original. |
| \`backend/tests/test_m39501_fastapi_route_attestation_ci.py\` | Falha proposital em cada situação de 404, indisponibilidade, verbo incorreto, app equivocado e health inválido. | Proíbe \`PASS\` indevido por mera existência de texto de rota no Git. |
| \`.github/workflows/frfinance-m39500-pg18-catalog-404-ci.yml\` | Suíte separada de regressão, sem banco de produção, sem credenciais nem migrações. | Job tem apenas \`contents: read\`, uso de checkout e pytest offline. |
| \`.github/workflows/validacao-atualizacao.yml\` | Suítes M39500/M39501 integradas antes do amplo teste de API e build APK. | Se houver falha, a compilação deve ficar bloqueada. |

## Interpretação responsável dos resultados

- \`PASS_OFFLINE_SOURCE_ONLY\`: SQL original e projeto versionados estão íntegros **no repositório**, mas o banco ainda **não foi examinado**.
- \`PASS_READ_ONLY_CATALOG\`: catálogo do banco original inspecionado sem escrita e compatível com as regras checadas. **Não é** um registro de migração/aplicação com proveniência comprovada, nem backup/restauração homologados.
- \`M39091_STATUS=PASS_READ_ONLY\`: o serviço carregado expõe as rotas GET exigidas e responde como FR Finance. Isso **não comprova** login, campanha carregada, ciclo aberto, crédito autorizado ou conexão PostgreSQL funcional.
- \`M39091_STATUS=BLOCKED_READ_ONLY\`: ambiente ou serviço insuficientemente comprovado. Não migrar nem mudar banco automaticamente.
- \`PRODUCTION_RELEASE=BLOCKED\`: situação de produção permanece independente do êxito da CI.

## Alinhamento com Caderno Mestre e Contrato Técnico

**P0-01: texto e divergências.** DR-03 já foi sanada por auditoria de código: \`com.frcaixinha.app\` é appId-base; \`.aistudio\` é sufixo debug intencional. Históricos e anexos continuam versionados. Informações antigas de “SQL candidata não aplicada” nos documentos são **fotografias de um momento anterior**; registros posteriores do operador relatam aplicação de SQL110/111 e SQL112/113, mas esta remessa **não afirma o estado persistente atual** sem leitura do banco. A verificação estrutural M39500 é o caminho seguro para conciliar o dado sem reaplicar versões antigas.

**P0-02: sistema e banco.** A API deve apresentar as rotas em execução e o Postgres original deve ser o único \`127.0.0.1:5433/frcaixinha_aistudio_dev\` com PGDATA original. Nunca apontar para o FR Caixinha 2.2, porta 5432, banco/roles do produto legado ou diretório de uma cópia.

**P0-03…P0-20:** a nova verificação de catálogo e rotas fornece apenas insumos específicos; nenhum dos demais 18 blocos (MFA, convites, consentimentos, backup/restore, OCI, Mercado Pago, Pix, encerramento anual, LGPD, Android/iOS release e testes E2E AT-01…50) é automaticamente aceito.

## Critérios de aceite da remessa

- [ ] CI específica M39500/M39501 concluída em \`SUCCESS\`.
- [ ] CI geral concluída em \`SUCCESS\`, com o APK debug construído sem regressão.
- [ ] Hash original de cada uma das quatro migrações confirmado.
- [ ] Simulações de fraude de RLS/permissão/identidade e diagnóstico 404 bloqueadas.
- [ ] Lista documental e histórico da PR #2 preservados.
- [ ] Nenhuma operação financeira real ativada ou autorizada por CI.
- [ ] Estado operacional original da API pós-reinício e PG18 obtidos **somente quando o ambiente estiver acessível**, com a autorização específica aplicável.
- [ ] Parecer externo/jurídico e GO final independentes dos resultados de código.

**Observação:** As duas primeiras caixas são critérios para verificar no GitHub; não devem ser marcadas antes do resultado da execução. As últimas exigem ambiente ou fornecedor externo e não podem ser “fechadas” artificialmente por desenvolvimento local.

## Próxima etapa operacional sem repetição de comandos

Os comandos de sincronização Git M39091 e de reinício FastAPI já foram executados pelo operador. **Não reiterar** esses procedimentos. O artefato novo executa apenas verificações novas, quando for apropriado testar o ambiente original. Se o backend não estiver acessível, o resultado correto é \`BLOCKED\` e não “problema resolvido”.

**Invariantes:** \`PIX_REAL=OFF\`; \`PAGAMENTOS_REAIS=OFF\`; \`ATIVACAO_REAL=OFF\`; \`PRODUCTION_RELEASE=BLOCKED\`; nenhum SQL de escrita, segundo banco, movimentação OCI, envio externo, assinatura ou instalação Android por esta remessa.
