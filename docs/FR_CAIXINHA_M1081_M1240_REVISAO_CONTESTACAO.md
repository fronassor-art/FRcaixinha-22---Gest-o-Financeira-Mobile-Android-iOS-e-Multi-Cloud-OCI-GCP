# FR Caixinha AI Studio — Macropacote M1081–M1240

Data: 04/11/2026. Base aprovada em GitHub + Termux: `3056591445182d8ca2e383d9e0995c017f687634`, CI #232 **6/6 PASS**. Branch `atualizacao-ai-studio-9b46a63187`; PR #2 **Draft, sem merge**. Projeto exclusivo AI Studio, não confundir com o projeto independente FRcaixinha 2.2.

## Diretriz de desenvolvimento
Concluir o aplicativo e testes no Oracle OCI **antes da etapa jurídica**. A ausência de aprovação jurídica não impede programação, integração, simulações ou testes. A ativação de pagamentos e outras operações financeiras reais continua separada e exige autorização aplicável.

## Problema real corrigido
A migration 028 registrava `PENDING_REVIEW` permanentemente na tabela de pedidos. Uma revisão iniciada por administrador tampouco aparecia ao membro afetado, porque 028 concedia leitura de pedidos próprios como solicitante. Isso impossibilitava contestar e não permitia que a fila mostrasse andamento real.

## Funcionalidade implementada neste pacote
1. `029_member_lifecycle_review_events.sql`: tabela **append-only** de eventos documentais, sequência monotônica, identidade do ator obtida da sessão, FK de tenant e membership, RLS forçada, idempotência e função definer de transição de fases. Membro sujeito à revisão recebe direito de leitura da solicitação através de nova política RLS restrita ao próprio vínculo.
2. Eventos previstos: `ADMIN_DOCUMENTS_REQUESTED`, `ADMIN_REVIEW_ACCEPTED_SANDBOX`, `ADMIN_REVIEW_REJECTED_SANDBOX`, `MEMBER_CONTESTED`. Essa aceitação é **documental de teste**, não validação jurídica nem mudança de direito patrimonial.
3. `member_lifecycle_reviews.py`: GET de capacidades da revisão, GET da linha de tempo do pedido e POST do próximo evento. Apenas sandbox explicitamente habilitado e não produção. O banco determina a autorização; cliente não envia identidade ou papel do aprovador.
4. Dual role e alçada: mesmo administrador que criou a solicitação não pode aprová-la; administrador que é sujeito como membro também não pode decidir o próprio caso. Revisões exigem um **segundo administrador independente** neste laboratório. Membro sujeito pode contestar, inclusive quando o pedido foi aberto pelo administrador.
5. `member_lifecycle_sandbox.py`: membro consulta pedidos em seu próprio vínculo, ainda que outro ator tenha aberto o caso; o contador de pendências de fechamento usa o evento mais recente, com decisão aceita/rejeitada reduzindo apenas a **pendência documental** e contestação reabrindo-a. Rateio, Pix, saída, bloqueio e fechamento reais permanecem negados.
6. Frontend: exibe a linha do tempo em cada pedido, ações de contestação e revisão apenas quando o backend divulga capacidade válida, exige confirmação explícita e reutiliza a chave de idempotência após erro.
7. CI: testes de parser e API com centenas de casos, testes SQL em duas versões de PostgreSQL descartável, cenário sintético com segundo administrador, contestação, rejeição, nova contestação, aceite e comprovação de nenhuma operação financeira.
8. **Migrations 028 e 029 NÃO aplicadas ao PostgreSQL 5433 do Termux**. Scripts de migração local mantêm a janela autorizada 001–027. O pacote de código pode ser sincronizado e testado em modo leitura, mas ações dependentes de 029 respondem 503 no ambiente não preparado.

## Limites técnicos que seguem explícitos
- Solicitações da tabela 028 continuam imutáveis e conservam `status=PENDING_REVIEW`, para fins de trilha. A linha de tempo 029 deriva o estado da revisão. O índice de um pedido ativo por membro/tipo/ciclo ainda impede **abrir uma segunda solicitação após uma revisão concluída**. Esta reutilização precisa ser implementada em próxima migração, sem apagar eventos anteriores.
- Sem prova de banco e de caixa não há lucro líquido rateável nem restituição; a mudança de status no laboratório **nunca** deve ser interpretada como sanção ou quitação.
- Ainda faltam fluxo de aceite real de documentação, notificações, revisão de alçadas para tenants com único administrador, conciliação Pix sandbox por recebedor, fechamento líquido, evidências de encargos, OCI staging e homologação física.

## Matriz de 160 controles
`IMPLEMENTADO/TESTE SUJEITO A CI` é apenas código e teste criados, não liberação comercial nem confirmação de CI. Os demais permanecem abertos.

| ID | Frente | Controle | Situação |
|---|---|---|---|
| M1081 | Autenticação e identidade | Sessão obrigatória para todas as rotas | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1082 | Autenticação e identidade | Master sem acesso aos casos do tenant | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1083 | Autenticação e identidade | Administrador com tenant válido | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1084 | Autenticação e identidade | Membro com vínculo próprio | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1085 | Autenticação e identidade | Terceiros de outro tenant bloqueados | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1086 | Autenticação e identidade | Sem identificação do ator fornecida pelo cliente | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1087 | Autenticação e identidade | Papel extraído exclusivamente da sessão | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1088 | Autenticação e identidade | Mesma pessoa com funções separadas | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1089 | Autenticação e identidade | Controle de acesso antes do SQL | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1090 | Autenticação e identidade | Troca de contexto invalida resposta da interface | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1091 | Pedidos de saída | Saída voluntária exige membro ativo | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1092 | Pedidos de saída | Referência contratual sintética | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1093 | Pedidos de saída | UUID idempotente da solicitação | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1094 | Pedidos de saída | Prova imutável de quem pediu | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1095 | Pedidos de saída | Ciclo e tenant vinculados | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1096 | Pedidos de saída | Fila imutável da solicitação 028 | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1097 | Pedidos de saída | Eventos documentais em tabela 029 | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1098 | Pedidos de saída | Admin diferente do solicitante | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1099 | Pedidos de saída | Decisão apenas técnica sem restituição | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1100 | Pedidos de saída | Saída não apaga direitos adquiridos | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1101 | Inadimplência e ciência | Revisão do administrador por membro | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1102 | Inadimplência e ciência | Membro afetado lê revisão aberta pelo admin | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1103 | Inadimplência e ciência | Contribuições por competência e ciclo preservadas | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1104 | Inadimplência e ciência | Distinguir três competências de 90 dias | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1105 | Inadimplência e ciência | Contestação antes da decisão | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1106 | Inadimplência e ciência | Pedido documental registrado com data | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1107 | Inadimplência e ciência | Segunda análise independente | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1108 | Inadimplência e ciência | Sem exclusão automática de rateio | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1109 | Inadimplência e ciência | Sem multa gerada por evento de revisão | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1110 | Inadimplência e ciência | Sem atualização de status membro pela função | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1111 | Contestações | Membro pode contestar seu processo | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1112 | Contestações | Contestação exige papel TENANT_MEMBER | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1113 | Contestações | Contestação de revisão aberta pelo admin | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1114 | Contestações | Contestação após solicitação de provas | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1115 | Contestações | Contestação após rejeição documental | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1116 | Contestações | Não contestar repetidamente o mesmo estado | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1117 | Contestações | Não alterar resultado bancário | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1118 | Contestações | Não criar lançamento contábil | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1119 | Contestações | Persistir todas as contestações | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1120 | Contestações | Fases derivadas do último evento | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1121 | Decisões administrativas | Solicitar documentos adicionais | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1122 | Decisões administrativas | Aceitar documentos tecnicamente | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1123 | Decisões administrativas | Rejeitar documentos tecnicamente | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1124 | Decisões administrativas | Não permitir decisão do próprio solicitante | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1125 | Decisões administrativas | Não permitir autoaprovação de membro dual | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1126 | Decisões administrativas | Exigir administrador registrado no tenant | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1127 | Decisões administrativas | Decisão terminal não aceita decisão nova direta | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1128 | Decisões administrativas | Rejeição admite contestação do membro | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1129 | Decisões administrativas | Nova decisão após contestação | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1130 | Decisões administrativas | Nenhuma decisão equivale a encerramento real | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1131 | Imutabilidade e idempotência | Eventos append-only | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1132 | Imutabilidade e idempotência | Sequência monotônica do banco | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1133 | Imutabilidade e idempotência | UUID próprio por evento | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1134 | Imutabilidade e idempotência | Chave idempotente por ator e pedido | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1135 | Imutabilidade e idempotência | Reenvio devolve mesmo evento | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1136 | Imutabilidade e idempotência | Chave com conteúdo diferente rejeitada | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1137 | Imutabilidade e idempotência | Trava de linha contra eventos concorrentes | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1138 | Imutabilidade e idempotência | Nenhum UPDATE concedido ao app | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1139 | Imutabilidade e idempotência | Nenhum DELETE concedido ao app | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1140 | Imutabilidade e idempotência | RLS forçada na tabela de eventos | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1141 | Persistência PostgreSQL | Migration 029 isolada em CI | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1142 | Persistência PostgreSQL | FK composta request/tenant | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1143 | Persistência PostgreSQL | FK composta membro/tenant | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1144 | Persistência PostgreSQL | Revisão restrita ao próprio tenant | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1145 | Persistência PostgreSQL | Referências alfanuméricas validadas | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1146 | Persistência PostgreSQL | Evento bancário sempre falso | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1147 | Persistência PostgreSQL | Evento financeiro sempre falso | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1148 | Persistência PostgreSQL | Índices por pedido e sequência | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1149 | Persistência PostgreSQL | Índice de trilha por ator | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1150 | Persistência PostgreSQL | Auditoria de grants ao final da migração | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1151 | API e respostas | GET review-capabilities | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1152 | API e respostas | GET review-events do pedido | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1153 | API e respostas | POST review-event em sandbox | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1154 | API e respostas | Modelos tipados em Pydantic | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1155 | API e respostas | 409 para conflito contratual | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1156 | API e respostas | 403 para papel incorreto | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1157 | API e respostas | 404 para pedido indisponível | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1158 | API e respostas | 503 sem migration 029 | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1159 | API e respostas | 100 eventos máximo sem truncamento enganoso | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1160 | API e respostas | Response sem poder de Pix ou fechamento | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1161 | Android e interface | Botão Ver análise por solicitação | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1162 | Android e interface | Linha do tempo em ordem de sequência | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1163 | Android e interface | Interface de admin com decisões técnicas | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1164 | Android e interface | Interface de membro com contestação | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1165 | Android e interface | Referência documental sem dados pessoais | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1166 | Android e interface | Confirmação explícita antes de gravar | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1167 | Android e interface | UUID aleatório seguro | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1168 | Android e interface | Idempotência preservada após erro | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1169 | Android e interface | Sem botões de dinheiro real | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1170 | Android e interface | Aviso de ausência de schema 029 | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1171 | Testes de fronteira | Parser estrito das capacidades | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1172 | Testes de fronteira | Parser estrito de eventos | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1173 | Testes de fronteira | Parser estrito de timeline | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1174 | Testes de fronteira | Rejeitar campos desconhecidos | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1175 | Testes de fronteira | Rejeitar evento de outro tenant | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1176 | Testes de fronteira | Rejeitar request ID trocado | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1177 | Testes de fronteira | Rejeitar eventos repetidos | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1178 | Testes de fronteira | Rejeitar sequência não crescente | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1179 | Testes de fronteira | Rejeitar estado final incompatível | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1180 | Testes de fronteira | Rejeitar privilégios financeiros verdadeiros | IMPLEMENTADO/TESTE SUJEITO A CI |
| M1181 | Livro-Razão e patrimônio | Não creditar capital por eventos de revisão | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1182 | Livro-Razão e patrimônio | Não cobrar multa de cota pela fila | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1183 | Livro-Razão e patrimônio | Não alterar contratos de empréstimo | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1184 | Livro-Razão e patrimônio | Não registrar juros sem prova | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1185 | Livro-Razão e patrimônio | Não criar lançamento Master SaaS | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1186 | Livro-Razão e patrimônio | Não distribuir lucro por aceite técnico | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1187 | Livro-Razão e patrimônio | Não emitir Pix de restituição | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1188 | Livro-Razão e patrimônio | Não alterar conta bancária do tenant | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1189 | Livro-Razão e patrimônio | Não confundir RLS com conciliação | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1190 | Livro-Razão e patrimônio | Provar ciclo sem fechamento efetuado | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1191 | Fechamento e rateio | Contar casos técnicos ainda pendentes | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1192 | Fechamento e rateio | Decisão aceita reduz pendência técnica | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1193 | Fechamento e rateio | Rejeição documental reduz pendência técnica | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1194 | Fechamento e rateio | Contestação reabre pendência | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1195 | Fechamento e rateio | Contribuição ainda não quitada bloqueia | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1196 | Fechamento e rateio | Empréstimo aberto impede liberação | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1197 | Fechamento e rateio | Banco ainda não reconciliado impede liquidação | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1198 | Fechamento e rateio | Capital-Dias exige prova de evento | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1199 | Fechamento e rateio | 15/85 somente do lucro aplicável | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1200 | Fechamento e rateio | Rateio em centavos só após fechamento autorizado | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1201 | Segregação Master e tenant | Master sem leitura de documentos privados | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1202 | Segregação Master e tenant | Master não revê caso de membro do tenant | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1203 | Segregação Master e tenant | Administrador da empresa A não aprova B | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1204 | Segregação Master e tenant | Membro de B não contesta revisão A | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1205 | Segregação Master e tenant | Vínculo duplo admin/membro rastreado | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1206 | Segregação Master e tenant | Receita SaaS não compõe capital | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1207 | Segregação Master e tenant | Valor de cota não remunera Master | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1208 | Segregação Master e tenant | Contas econômicas não cruzam tenant | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1209 | Segregação Master e tenant | Mesmo UUID fora do tenant não autoriza | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1210 | Segregação Master e tenant | RLS de leitura de evento por membro | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1211 | Laboratórios CI | PostgreSQL 16 descartável | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1212 | Laboratórios CI | PostgreSQL 18 descartável | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1213 | Laboratórios CI | Migrações 001–029 em ordem | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1214 | Laboratórios CI | Roles não-superuser no app | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1215 | Laboratórios CI | Duas caixinhas sintéticas | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1216 | Laboratórios CI | Dez vínculos base | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1217 | Laboratórios CI | Revisor independente sintético | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1218 | Laboratórios CI | Contestação com decisão rejeitada | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1219 | Laboratórios CI | Recontestação e novo aceite | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1220 | Laboratórios CI | Checagem de nenhuma alteração financeira | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1221 | Operação em OCI | Provisionar sandbox OCI separado | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1222 | Operação em OCI | Configurar HTTPS no backend | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1223 | Operação em OCI | Executar migrations aprovadas em staging | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1224 | Operação em OCI | Segredos no OCI Vault | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1225 | Operação em OCI | Monitorar fila e logs de revisão | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1226 | Operação em OCI | Provar recuperação de banco | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1227 | Operação em OCI | Testar concorrência de decisões | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1228 | Operação em OCI | Testar políticas com ambiente desligado | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1229 | Operação em OCI | Homologar Android contra staging | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1230 | Operação em OCI | Registrar evidência de custos e disponibilidade | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1231 | Conclusão e governança | Conferir 147 cláusulas com o Caderno | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1232 | Conclusão e governança | Não bloquear codificação por fase jurídica | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1233 | Conclusão e governança | Homologar OCI antes da revisão jurídica | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1234 | Conclusão e governança | Continuar PR #2 como Draft | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1235 | Conclusão e governança | Não migrar banco Termux 5433 sem autorização | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1236 | Conclusão e governança | Executar frontend/PG16/PG18 antes de APK | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1237 | Conclusão e governança | Validar commit SHA exato | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1238 | Conclusão e governança | Rastrear recursos e alçadas pendentes | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1239 | Conclusão e governança | Não declarar pagamento autorizado por teste | PENDENTE DE INTEGRAÇÃO COMPLETA |
| M1240 | Conclusão e governança | Separar ativação financeira do desenvolvimento | PENDENTE DE INTEGRAÇÃO COMPLETA |

## Próxima verificação
Apenas GitHub Actions no SHA deste pacote pode promovê-lo: API, frontend, PG16, PG18, snapshot fonte e APK (seis jobs). Não executar comandos de migrar banco local até revisão explícita.
