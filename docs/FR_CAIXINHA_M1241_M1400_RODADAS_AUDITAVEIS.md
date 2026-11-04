# FR Caixinha AI Studio — Macropacote M1241–M1400

Data: 04/11/2026. Base **comprovada em Termux**: `3056591445182d8ca2e383d9e0995c017f687634`, M1080, CI #232 (6/6 PASS). M1240 `634513ef9d698a1d3b9f869f1b9d4a6258da5ade` apresentou CI #233 FAIL em expectativas de testes antigas; commit corretivo intermediário `c748db04eedc47adff4e3f286ce7eb5391964c3e` submetido à CI #234. A CI #234 também evidenciou teste estático da migração 028 indevidamente fixado em `seq 1 28`, enquanto a branch atual já possuía 029.

## Escopo efetivamente implementado

- **M030** `backend/migrations/030_member_lifecycle_case_rounds.sql`: substitui SOMENTE a função definer `lifecycle_submit_request_sandbox`. Remove índice antigo que bloqueava qualquer nova rodada no mesmo ciclo; adiciona índice de busca histórica; serializa pedidos por `tenant/ciclo/membro/tipo` com advisory lock transacional. Uma nova solicitação é aberta **somente** após a última revisão documental concluir (evento de aceite ou rejeição); com revisão pendente, retorna a mesma solicitação se ator/política coincidirem. Reutilizar chave antiga retorna seu UUID histórico, mesmo após nova rodada; reutilizar chave histórica sob outra política/ator/ciclo é erro.
- **App e API:** listagens de solicitações agora retornam `latest_review_event` e `technical_review_pending`, obtidos por LATERAL ao último evento com RLS. A interface distingue "pedido histórico PENDING_REVIEW" da revisão técnica concluída. Nenhuma decisão financeira é deduzida dos eventos.
- **Testes reais PostgreSQL 16/18:** simulam saída, revisão, aceite, rejeição, contestação, novo pedido, reenvio idempotente, conflito histórico, reabertura por tipo, isolamento RLS e 16 tentativas concorrentes reais com conexões distintas.
- **Testes locais sem banco:** 160 casos de leitura de estado + 240 casos de comportamento de terminalidade e segurança SQL, além de verificações TypeScript. O foco não é inflar números de tarefas; os testes têm entradas e asserts, enquanto cenários em atraso continuam no backlog.
- **CI:** migra 001–030 em laboratórios PostgreSQL descartáveis 16/18; fixa a verificação do script de migração 028 para **aceitar versões sucessoras**, exigir arquivos SQL contínuos e manter banco exclusivo `frcaixinha_ci`.
- **Nenhuma migration 028/029/030 foi aplicada ao banco persistente 5433**. A aplicação do pacote não deve alterar Termux até validação, e em nenhuma fase permite Pix real.

## Riscos e pendências explícitas

- Reabertura de pedido é apenas técnica/sintética e não representa novo contrato de adesão, reintegração financeira ou restituição.
- A função `lifecycle_submit_request_sandbox` exige papel e identidade válidos e não modifica status de membro; é uma proteção para código de homologação, não um substituto para decisão contratual.
- A definição de três meses inadimplentes, 90 dias, juros/multas, saídas e elegibilidade para o rateio **continua lastreada no Caderno/Contrato Técnico Mestre já aprovados**. Esta etapa não altera nem inventa suas regras.
- Ainda faltam efeitos jurídicos/financeiros contratuais transformados em eventos contabilizáveis, reconciliação Mercado Pago sandbox multiempresa, Oracle OCI staging, homologação completa Android e limites de paginação da fila.

## Matriz M1241–M1400 — 160 controles

O estado `CÓDIGO/TESTE NOVO — CI PENDENTE` significa que houve implementação/teste associado a esta etapa e que **ainda depende de GitHub Actions do SHA exato**. `PENDENTE DE FLUXO OPERACIONAL` significa não concluído.

| ID | Frente | Controle | Estado |
|---|---|---|---|
| M1241 | Histórico preservado | Pedido 028 permanece imutável | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1242 | Histórico preservado | Eventos 029 permanecem append-only | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1243 | Histórico preservado | Solicitação antiga continua consultável | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1244 | Histórico preservado | Autoria anterior fica preservada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1245 | Histórico preservado | Política anterior fica preservada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1246 | Histórico preservado | Revisão antiga continua por request_id | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1247 | Histórico preservado | Nova rodada recebe novo UUID | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1248 | Histórico preservado | Histórico não apaga contestação | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1249 | Histórico preservado | Status base PENDING_REVIEW permanece histórico | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1250 | Histórico preservado | Último evento define apenas fase documental | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1251 | Idempotência de requisições | Mesma chave antiga retorna UUID original | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1252 | Idempotência de requisições | Chave antiga com política diferente rejeitada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1253 | Idempotência de requisições | Chave antiga com ator diferente rejeitada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1254 | Idempotência de requisições | Chave antiga de outro ciclo rejeitada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1255 | Idempotência de requisições | Nova chave com rodada pendente retorna mesma rodada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1256 | Idempotência de requisições | Nova chave após conclusão abre nova rodada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1257 | Idempotência de requisições | Mesmo membro por mesmo tipo não duplica pendência | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1258 | Idempotência de requisições | Tipos saída e revisão permanecem separados | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1259 | Idempotência de requisições | Outros membros não compartilham chave | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1260 | Idempotência de requisições | Outros tenants não compartilham processo | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1261 | Serialização PostgreSQL | Advisory lock transacional por escopo | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1262 | Serialização PostgreSQL | Lock inclui tenant | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1263 | Serialização PostgreSQL | Lock inclui ciclo | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1264 | Serialização PostgreSQL | Lock inclui membro | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1265 | Serialização PostgreSQL | Lock inclui tipo da solicitação | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1266 | Serialização PostgreSQL | Concorrência sem linha existente protegida | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1267 | Serialização PostgreSQL | 16 pedidos concorrentes testados | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1268 | Serialização PostgreSQL | Somente uma linha criada entre concorrentes | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1269 | Serialização PostgreSQL | Reenvios concorrentes retornam identificador único | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1270 | Serialização PostgreSQL | Consulta lê última rodada por data e UUID | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1271 | Estados de revisão | Sem evento não pode reabrir | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1272 | Estados de revisão | Documentos solicitados não libera nova rodada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1273 | Estados de revisão | Contestação em andamento não libera | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1274 | Estados de revisão | Aceite documental permite nova rodada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1275 | Estados de revisão | Rejeição documental permite nova rodada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1276 | Estados de revisão | Recontestação reabre a pendência documental | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1277 | Estados de revisão | Novas rodadas reiniciam análise documental | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1278 | Estados de revisão | Estado financeiro não deriva da revisão | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1279 | Estados de revisão | Decisão jurídica não é presumida | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1280 | Estados de revisão | Nenhum dinheiro é movimentado pela transição | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1281 | Segurança RLS e papéis | Master não recebe acesso a solicitações | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1282 | Segurança RLS e papéis | Admin só lê pedidos do tenant | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1283 | Segurança RLS e papéis | Membro só lê pedidos sobre seu vínculo | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1284 | Segurança RLS e papéis | Autor do pedido é derivado de sessão | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1285 | Segurança RLS e papéis | Tenant é verificado na função SQL | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1286 | Segurança RLS e papéis | Admin precisa ser papel ativo do tenant | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1287 | Segurança RLS e papéis | Membro de saída precisa estar ativo | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1288 | Segurança RLS e papéis | Revisão permite vínculo válido no tenant | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1289 | Segurança RLS e papéis | App role não recebe INSERT direto | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1290 | Segurança RLS e papéis | Auth role não recebe EXECUTE da função | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1291 | Ciclos e contratos | Somente ciclo elegível aceita nova solicitação | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1292 | Ciclos e contratos | Requisição permanece vinculada ao ciclo | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1293 | Ciclos e contratos | Nova rodada não muda política aprovada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1294 | Ciclos e contratos | Histórico idempotente respeita o ciclo original | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1295 | Ciclos e contratos | Saída voluntária segue fluxo próprio | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1296 | Ciclos e contratos | Inadimplência segue revisão separada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1297 | Ciclos e contratos | Verificação de versão documental é sintática | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1298 | Ciclos e contratos | Nenhuma nova regra de multa foi presumida | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1299 | Ciclos e contratos | Nenhuma nova regra de rateio foi presumida | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1300 | Ciclos e contratos | Contrato Mestre continua fonte normativa | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1301 | API FastAPI | GET de membro continua com autenticação | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1302 | API FastAPI | GET de administrador continua segregado | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1303 | API FastAPI | POST usa função SQL restrita | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1304 | API FastAPI | HTTP 409 indica conflito de política | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1305 | API FastAPI | HTTP 503 indica schema ausente | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1306 | API FastAPI | Novo estado derivado é retornado na lista | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1307 | API FastAPI | Último evento de revisão é explícito | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1308 | API FastAPI | Estado técnico pendente é booleano | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1309 | API FastAPI | Resposta não inclui saldo bancário | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1310 | API FastAPI | Resposta não concede autorização de fechamento | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1311 | Interface mobile | Fila distingue pedido e revisão documental | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1312 | Interface mobile | Estado pendente mostrado conforme último evento | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1313 | Interface mobile | Estado concluído mostrado após decisão | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1314 | Interface mobile | Último evento aparece na tela | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1315 | Interface mobile | Pedido histórico permanece visível | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1316 | Interface mobile | Mensagem alerta que direito patrimonial não mudou | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1317 | Interface mobile | Parser rejeita evento desconhecido | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1318 | Interface mobile | Parser rejeita conclusão contraditória | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1319 | Interface mobile | Parser rejeita campo financeiro inesperado | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1320 | Interface mobile | Solicitação no app continua idempotente | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1321 | Testes automatizados | 160 variantes de estado registral | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1322 | Testes automatizados | 240 combinações parametrizadas de estado 030 | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1323 | Testes automatizados | PostgreSQL 16 descartável | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1324 | Testes automatizados | PostgreSQL 18 descartável | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1325 | Testes automatizados | CI aplica migrations 001–030 | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1326 | Testes automatizados | Teste funcional de segunda rodada | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1327 | Testes automatizados | Teste de retorno de pedido histórico | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1328 | Testes automatizados | Teste de política divergente | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1329 | Testes automatizados | Teste de 16 concorrentes simultâneos | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1330 | Testes automatizados | Teste de ausência de efeitos financeiros | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1331 | Fechamento contábil | Revisão concluída sai da pendência documental | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1332 | Fechamento contábil | Nova rodada reabre pendência documental | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1333 | Fechamento contábil | Contribuições em aberto permanecem | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1334 | Fechamento contábil | Empréstimos não quitados permanecem | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1335 | Fechamento contábil | Saldo bancário não é presumido | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1336 | Fechamento contábil | Sem fechamento automático | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1337 | Fechamento contábil | Sem rateio liberado pela revisão | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1338 | Fechamento contábil | Sem movimentação real | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1339 | Fechamento contábil | Histórico da caixinha mantém auditoria | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1340 | Fechamento contábil | Fechamento real exige conciliação própria | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1341 | Inadimplência operacional | Detectar três competências consecutivas | PENDENTE DE FLUXO OPERACIONAL |
| M1342 | Inadimplência operacional | Separar noventa dias de atraso | PENDENTE DE FLUXO OPERACIONAL |
| M1343 | Inadimplência operacional | Versão da regra por ciclo | PENDENTE DE FLUXO OPERACIONAL |
| M1344 | Inadimplência operacional | Provar constituição da mora | PENDENTE DE FLUXO OPERACIONAL |
| M1345 | Inadimplência operacional | Calcular encargos monetários com Decimal | PENDENTE DE FLUXO OPERACIONAL |
| M1346 | Inadimplência operacional | Persistir notificação de bloqueio | PENDENTE DE FLUXO OPERACIONAL |
| M1347 | Inadimplência operacional | Aplicar bloqueio de novas operações | PENDENTE DE FLUXO OPERACIONAL |
| M1348 | Inadimplência operacional | Respeitar direitos de capital preservados | PENDENTE DE FLUXO OPERACIONAL |
| M1349 | Inadimplência operacional | Determinar elegibilidade de rateio pela cláusula | PENDENTE DE FLUXO OPERACIONAL |
| M1350 | Inadimplência operacional | Regularização com trilha auditável | PENDENTE DE FLUXO OPERACIONAL |
| M1351 | Saída e desligamento | Solicitação do membro autenticado | PENDENTE DE FLUXO OPERACIONAL |
| M1352 | Saída e desligamento | Aceite documental independente | PENDENTE DE FLUXO OPERACIONAL |
| M1353 | Saída e desligamento | Provar valores devidos pelo membro | PENDENTE DE FLUXO OPERACIONAL |
| M1354 | Saída e desligamento | Apurar capital quitado por competência | PENDENTE DE FLUXO OPERACIONAL |
| M1355 | Saída e desligamento | Aplicar regra de saída voluntária do contrato | PENDENTE DE FLUXO OPERACIONAL |
| M1356 | Saída e desligamento | Calcular devolução contratual exata | PENDENTE DE FLUXO OPERACIONAL |
| M1357 | Saída e desligamento | Contabilizar obrigações de restituição | PENDENTE DE FLUXO OPERACIONAL |
| M1358 | Saída e desligamento | Testar calendário e prazos de pagamento | PENDENTE DE FLUXO OPERACIONAL |
| M1359 | Saída e desligamento | Reconciliar Pix de devolução no sandbox | PENDENTE DE FLUXO OPERACIONAL |
| M1360 | Saída e desligamento | Encerrar vínculo apenas após critérios completos | PENDENTE DE FLUXO OPERACIONAL |
| M1361 | Resultado e rateio | Apurar lucro líquido realizado | PENDENTE DE FLUXO OPERACIONAL |
| M1362 | Resultado e rateio | Deduzir despesas e perdas comprovadas | PENDENTE DE FLUXO OPERACIONAL |
| M1363 | Resultado e rateio | Separar capital social do lucro | PENDENTE DE FLUXO OPERACIONAL |
| M1364 | Resultado e rateio | Aplicar percentual vigente do tenant | PENDENTE DE FLUXO OPERACIONAL |
| M1365 | Resultado e rateio | Manter receita SaaS fora do caixa da caixinha | PENDENTE DE FLUXO OPERACIONAL |
| M1366 | Resultado e rateio | Aplicar capital-dias em America/Belem | PENDENTE DE FLUXO OPERACIONAL |
| M1367 | Resultado e rateio | Aplicar sanções de elegibilidade contratadas | PENDENTE DE FLUXO OPERACIONAL |
| M1368 | Resultado e rateio | Calcular maiores restos em centavos | PENDENTE DE FLUXO OPERACIONAL |
| M1369 | Resultado e rateio | Destinar resíduos à carteira segregada | PENDENTE DE FLUXO OPERACIONAL |
| M1370 | Resultado e rateio | Gerar extrato do beneficiário | PENDENTE DE FLUXO OPERACIONAL |
| M1371 | Pagamentos multiempresa | OAuth Connect por recebedor | PENDENTE DE FLUXO OPERACIONAL |
| M1372 | Pagamentos multiempresa | Tokens apenas no backend | PENDENTE DE FLUXO OPERACIONAL |
| M1373 | Pagamentos multiempresa | Pagamentos Pix apenas em sandbox | PENDENTE DE FLUXO OPERACIONAL |
| M1374 | Pagamentos multiempresa | Assinatura SaaS recebida na plataforma | PENDENTE DE FLUXO OPERACIONAL |
| M1375 | Pagamentos multiempresa | Contribuições recebidas em conta do tenant | PENDENTE DE FLUXO OPERACIONAL |
| M1376 | Pagamentos multiempresa | Webhook autenticado e deduplicado | PENDENTE DE FLUXO OPERACIONAL |
| M1377 | Pagamentos multiempresa | GET autoritativo do provedor | PENDENTE DE FLUXO OPERACIONAL |
| M1378 | Pagamentos multiempresa | Reversões e estornos rastreados | PENDENTE DE FLUXO OPERACIONAL |
| M1379 | Pagamentos multiempresa | Comprovantes bancários contra ledger | PENDENTE DE FLUXO OPERACIONAL |
| M1380 | Pagamentos multiempresa | Real money permanece desabilitado | PENDENTE DE FLUXO OPERACIONAL |
| M1381 | Oracle OCI e Android | Provisionar staging isolado na OCI | PENDENTE DE FLUXO OPERACIONAL |
| M1382 | Oracle OCI e Android | Configurar banco separado do Termux | PENDENTE DE FLUXO OPERACIONAL |
| M1383 | Oracle OCI e Android | Prover segredos em Vault | PENDENTE DE FLUXO OPERACIONAL |
| M1384 | Oracle OCI e Android | Configurar HTTPS e DNS | PENDENTE DE FLUXO OPERACIONAL |
| M1385 | Oracle OCI e Android | Rodar migrations no staging aprovado | PENDENTE DE FLUXO OPERACIONAL |
| M1386 | Oracle OCI e Android | Homologar API com usuários fictícios | PENDENTE DE FLUXO OPERACIONAL |
| M1387 | Oracle OCI e Android | Testar carga e concorrência | PENDENTE DE FLUXO OPERACIONAL |
| M1388 | Oracle OCI e Android | Validar backup e restauração | PENDENTE DE FLUXO OPERACIONAL |
| M1389 | Oracle OCI e Android | Instalar APK compilado no aparelho | PENDENTE DE FLUXO OPERACIONAL |
| M1390 | Oracle OCI e Android | Concluir testes antes da fase jurídica | PENDENTE DE FLUXO OPERACIONAL |
| M1391 | Governança final | GitHub PR #2 permanece Draft | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1392 | Governança final | Branch preserva histórico Git | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1393 | Governança final | Commit novo exige CAS de SHA | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1394 | Governança final | CI verifica PG16 e PG18 | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1395 | Governança final | Android somente depois dos gates | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1396 | Governança final | Termux 5433 não recebe migração | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1397 | Governança final | Nenhum pagamento real foi executado | CÓDIGO/TESTE NOVO — CI PENDENTE |
| M1398 | Governança final | Tarefas não implementadas permanecem abertas | PENDENTE DE FLUXO OPERACIONAL |
| M1399 | Governança final | Leitura jurídica não bloqueia o desenvolvimento | PENDENTE DE FLUXO OPERACIONAL |
| M1400 | Governança final | Ativação comercial vem após homologação e autorizações | PENDENTE DE FLUXO OPERACIONAL |

## Gatilhos obrigatórios para sincronização

Verificar GitHub Actions (frontend, API, PostgreSQL 16, PostgreSQL 18, fonte, Android), **todas as 6 etapas PASS** para o commit exato; PR #2 permanece Draft. Depois, sincronizar no Termux `git merge --ff-only` com BASE `3056591` e TARGET igual ao novo SHA, sem aplicar migrations locais. Reiniciar somente o FastAPI ao incorporar a nova versão, preservando o PostgreSQL 5433.

**Não confundir FR Caixinha AI Studio com o projeto independente FRcaixinha 2.2. O fato de a etapa jurídica ser posterior não bloqueia codificação/homologação OCI; operações financeiras reais continuam separadas.**
