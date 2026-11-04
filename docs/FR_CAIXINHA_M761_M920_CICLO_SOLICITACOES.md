# FR Caixinha AI Studio — M761–M920: 160 controles de ciclo, saída e bloqueio

Data: 04/11/2026. Baseline local comprovado: `6cf856ce3840f72760f4ce53e690f7712359d468`. Macropacote M601–M760 em avaliação na CI #228, commit `c92c72b2c672708b569edf6d1a512f2b0bdebc68`. Projeto independente da outra frente FRcaixinha 2.2.

## Entrega técnica desta etapa — comprovar pelo SHA final da CI

### Persistência: migration 028 SOMENTE em bancos CI descartáveis
- `backend/migrations/028_member_lifecycle_sandbox_requests.sql`: pedidos de saída `VOLUNTARY_EXIT` e revisão `DELINQUENCY_REVIEW` por tenant/cycle/membership, com idempotência, política de referência, estado imutável `PENDING_REVIEW`, data, acesso RLS separado e referências compostas que impedem tenant cruzado.
- Função SQL `public.lifecycle_submit_request_sandbox(...)`: verifica contexto extraído exclusivamente da sessão, vínculo ativo do membro e autorização do administrador. **Não altera status da associação, direitos, cotas, lucro, mora, Livro-Razão ou Pix.**
- A tabela só permite SELECT ao papel de aplicação; a única inclusão ocorre por função SQL verificada. Nenhum UPDATE/DELETE é concedido ao app/auth. Um pedido repetido não gera nova obrigação.
- Migrations em CI: PostgreSQL 16 e PostgreSQL 18 incluem `028`. Os scripts locais de Termux continuam FIXADOS em `001–027`; aplicar 028 ao banco persistente não está autorizado nesta fase. A nova rota, quando não encontra o esquema, falha com indisponibilidade em vez de inventar dados.

### Rotas e painel
- `GET /api/v1/tenants/{tenant_id}/cycles/{year}/member-lifecycle/me`: apenas pedidos próprios.
- `GET /api/v1/tenants/{tenant_id}/cycles/{year}/member-lifecycle/admin-queue`: fila consolidada apenas para administrador daquele tenant.
- `POST /api/v1/tenants/{tenant_id}/cycles/{year}/member-lifecycle/me/voluntary-exit`: apenas membro ativo, requer `FRCAIXINHA_LIFECYCLE_SANDBOX=1` e `ENVIRONMENT != production`.
- `POST /api/v1/tenants/{tenant_id}/cycles/{year}/member-lifecycle/members/{membership_id}/delinquency-review`: apenas administrador daquele tenant, sujeito ao mesmo gate e a validação SQL.
- Na produção, o POST responde **503**, mesmo se alguém ligar a flag. Isso é um bloqueio de ativação financeira, não de desenvolvimento/teste.
- `src/components/MemberLifecyclePanel.tsx`: fila de consultas em Membro/Admin; aviso se servidor ainda não migrou. Parser cliente rejeita estados como `LIQUIDADO`, saldos e privilégios que não existem no contrato da fila.

### Testes e demonstrações
- `backend/tests/test_member_lifecycle_sandbox_ci.py`: autorizações, 121 idempotency keys, 403, 503, estado de efeitos desligados.
- `src/tests/member_lifecycle_sandbox_ci.test.ts`: 140 cenários de parser e fronteiras de escopo, além de malformações.
- `backend/tests/test_aistudio_financial_lab_integrated_ci.py`: laboratório real PostgreSQL 16/18 com pessoas fictícias, pedidos reais de banco descartável, idempotência, leitura RLS por membro e admin, duplicata, negados cross-tenant, acesso SQL direto a UPDATE negado; sem mutações financeiras.
- **NÃO declarar a CI aprovada** antes do GitHub Actions do SHA correto. A matriz abaixo mistura controles implementados neste pacote e controles do backlog operacional; nenhum indicador é promovido sem prova.

## Matriz de 160 controles M761–M920
| ID | Frente | Controle | Estado previsto |
|---|---|---|---|
| M761 | Identidade e autorização | Sessão verificável | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M762 | Identidade e autorização | Contexto do tenant por servidor | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M763 | Identidade e autorização | Master sem fila individual | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M764 | Identidade e autorização | Admin só próprio tenant | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M765 | Identidade e autorização | Membro só próprio vínculo | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M766 | Identidade e autorização | Membro impedido de revisar terceiros | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M767 | Identidade e autorização | Admin impedido de pedir saída por terceiro | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M768 | Identidade e autorização | Usuário de outro tenant sem acesso | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M769 | Identidade e autorização | Nome e CPF ausentes no payload | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M770 | Identidade e autorização | Troca de sessão invalida consulta | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M771 | Pedidos voluntários | Pedido formal de membro ativo | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M772 | Pedidos voluntários | Identificador UUID de requisição | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M773 | Pedidos voluntários | Idempotência por UUID | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M774 | Pedidos voluntários | Evidência documental referenciada | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M775 | Pedidos voluntários | Ciclo pertence ao tenant | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M776 | Pedidos voluntários | Diferenciar pedido e aprovação | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M777 | Pedidos voluntários | Estado inicial pendente | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M778 | Pedidos voluntários | Data registrada em UTC | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M779 | Pedidos voluntários | Sem alteração de membership | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M780 | Pedidos voluntários | Sem movimentação de caixa | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M781 | Revisão de inadimplência | Somente admin de tenant | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M782 | Revisão de inadimplência | Membro alvo do mesmo tenant | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M783 | Revisão de inadimplência | Só vínculos membro válidos | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M784 | Revisão de inadimplência | Admin não decide automaticamente | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M785 | Revisão de inadimplência | Pedido de revisão distinto de saída | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M786 | Revisão de inadimplência | Fila filtrada por exercício | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M787 | Revisão de inadimplência | Data de evento auditável | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M788 | Revisão de inadimplência | Histórico mensal não alterado | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M789 | Revisão de inadimplência | Sem perda automática de rateio | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M790 | Revisão de inadimplência | Sem multa criada pela fila | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M791 | Isolamento PostgreSQL | Tabela nova FORCE RLS | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M792 | Isolamento PostgreSQL | SELECT próprio membro | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M793 | Isolamento PostgreSQL | SELECT de admin do tenant | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M794 | Isolamento PostgreSQL | MASTER não lê | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M795 | Isolamento PostgreSQL | Auth role sem SELECT | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M796 | Isolamento PostgreSQL | Verifier role sem SELECT | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M797 | Isolamento PostgreSQL | App role sem INSERT direto | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M798 | Isolamento PostgreSQL | App role sem UPDATE direto | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M799 | Isolamento PostgreSQL | App role sem DELETE direto | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M800 | Isolamento PostgreSQL | Função definer valida contexto | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M801 | Provas e repetição | Duplicata mesma chave retorna ID | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M802 | Provas e repetição | Outra chave não duplica solicitação pendente | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M803 | Provas e repetição | Revisão e saída são eventos distintos | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M804 | Provas e repetição | Outro ano não reutiliza fila | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M805 | Provas e repetição | Outra caixinha não compartilha chave | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M806 | Provas e repetição | Política conflitante rejeitada | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M807 | Provas e repetição | Confirmação de escrita no PostgreSQL | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M808 | Provas e repetição | Prova com documento sintético | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M809 | Provas e repetição | Sem status FINISHED implícito | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M810 | Provas e repetição | Fila mantém ordem temporal | TESTE/IMPLEMENTAÇÃO NESTE PACOTE |
| M811 | Contrato mestre | Versão vinculada ao ciclo | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M812 | Contrato mestre | Cláusula especial 3 competências | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M813 | Contrato mestre | 90 dias indicador separado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M814 | Contrato mestre | Capital principal preservado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M815 | Contrato mestre | Quitação tardia no histórico | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M816 | Contrato mestre | Saída adimplente mantém direitos adquiridos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M817 | Contrato mestre | Outras caixinhas mantêm política própria | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M818 | Contrato mestre | Direito a lucro só após apuração válida | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M819 | Contrato mestre | Cálculo de mora com base contratual | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M820 | Contrato mestre | Jurídico após conclusão técnica/OCI | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M821 | Ledger e capital | Livro com lançamentos balanceados | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M822 | Ledger e capital | Contribuição associada a referência | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M823 | Ledger e capital | Conta 1.1.1 caixa tenant | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M824 | Ledger e capital | Conta 2.1.1 capital membro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M825 | Ledger e capital | Diferença de centavos detectada | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M826 | Ledger e capital | Saldo cadastral não é saldo bancário | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M827 | Ledger e capital | Principal devolvido só após prova | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M828 | Ledger e capital | Não misturar caixa Master e tenant | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M829 | Ledger e capital | Estorno preserva trilha | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M830 | Ledger e capital | Integridade sob concorrência | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M831 | Fluxo de saída | Solicitação registrada pelo membro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M832 | Fluxo de saída | Admin recebe pedido na fila | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M833 | Fluxo de saída | Consultar direitos e dívidas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M834 | Fluxo de saída | Congelar snapshot de apuração | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M835 | Fluxo de saída | Registrar consentimentos documentais | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M836 | Fluxo de saída | Aprovação independente | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M837 | Fluxo de saída | Calcular restituição admissível | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M838 | Fluxo de saída | Criar obrigação de pagamento | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M839 | Fluxo de saída | Conciliar Pix de restituição | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M840 | Fluxo de saída | Encerrar vínculo após cumprimento | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M841 | Fluxo de bloqueio | Detectar inadimplência contratual | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M842 | Fluxo de bloqueio | Abrir revisão administrativa | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M843 | Fluxo de bloqueio | Notificação ao membro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M844 | Fluxo de bloqueio | Permitir contestação auditável | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M845 | Fluxo de bloqueio | Revisar documentação e dias | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M846 | Fluxo de bloqueio | Bloquear novas operações elegíveis | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M847 | Fluxo de bloqueio | Não apagar quotas ou saldos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M848 | Fluxo de bloqueio | Preservar registro de regularização | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M849 | Fluxo de bloqueio | Provar aplicação de política do ciclo | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M850 | Fluxo de bloqueio | Restabelecer poderes quando contratado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M851 | Encerramento total da caixinha | Solicitação distinta de membro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M852 | Encerramento total da caixinha | Admin responsável autorizado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M853 | Encerramento total da caixinha | Mapa de passivos/ativos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M854 | Encerramento total da caixinha | Reservas e créditos em aberto | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M855 | Encerramento total da caixinha | Obrigação com terceiros | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M856 | Encerramento total da caixinha | Documentos de encerramento | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M857 | Encerramento total da caixinha | Notificações auditadas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M858 | Encerramento total da caixinha | Conciliação de todos os caixas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M859 | Encerramento total da caixinha | Separação de assinatura SaaS | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M860 | Encerramento total da caixinha | Desativação só após liquidação | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M861 | Motor de lucro | Receitas recebidas e conciliadas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M862 | Motor de lucro | Despesas elegíveis deduzidas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M863 | Motor de lucro | Perdas documentadas deduzidas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M864 | Motor de lucro | Capital de cota fora de lucro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M865 | Motor de lucro | Encargos vencidos alocados | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M866 | Motor de lucro | Parcela Price correta | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M867 | Motor de lucro | Admin 15% sobre lucro no tenant inaugural | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M868 | Motor de lucro | Membros 85% do pool elegível | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M869 | Motor de lucro | Outros tenants com política própria | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M870 | Motor de lucro | Precisão e maiores restos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M871 | Motor de rateio | Capital-Dias V2 diário | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M872 | Motor de rateio | Fuso America/Belem | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M873 | Motor de rateio | Peso zero se sanção válida | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M874 | Motor de rateio | Direito do desligado regular | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M875 | Motor de rateio | Resíduo técnico separado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M876 | Motor de rateio | Empate por membership_id | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M877 | Motor de rateio | Dinheiro suficiente antes de pagar | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M878 | Motor de rateio | Snapshot imutável de cálculo | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M879 | Motor de rateio | Comprovante individual do rateio | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M880 | Motor de rateio | Não pagar se revisão pendente | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M881 | Pix e Mercado Pago sandbox | Credencial Master separada | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M882 | Pix e Mercado Pago sandbox | OAuth de cada vendedor | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M883 | Pix e Mercado Pago sandbox | Sandbox sem dinheiro real | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M884 | Pix e Mercado Pago sandbox | Idempotência provider | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M885 | Pix e Mercado Pago sandbox | Webhook HMAC | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M886 | Pix e Mercado Pago sandbox | Replay/expiração | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M887 | Pix e Mercado Pago sandbox | GET autoritativo | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M888 | Pix e Mercado Pago sandbox | Baixa transacional única | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M889 | Pix e Mercado Pago sandbox | Chargeback e reembolso | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M890 | Pix e Mercado Pago sandbox | Transações rejeitadas sem contabilização | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M891 | Segurança e infraestrutura | Migrations apenas PG descartável | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M892 | Segurança e infraestrutura | Termux 5433 intocado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M893 | Segurança e infraestrutura | Oracle OCI staging isolado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M894 | Segurança e infraestrutura | OCI Vault de segredos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M895 | Segurança e infraestrutura | HTTPS e certificados | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M896 | Segurança e infraestrutura | RLS comprovado com duas empresas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M897 | Segurança e infraestrutura | Backup e restore ensaiado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M898 | Segurança e infraestrutura | Logs sem dados sensíveis | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M899 | Segurança e infraestrutura | Testes de carga e concorrência | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M900 | Segurança e infraestrutura | Observabilidade de workers | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M901 | Painéis e Android | Fila leitura no perfil Membro | CLIENTE EM IMPLEMENTAÇÃO |
| M902 | Painéis e Android | Fila leitura no perfil Admin | CLIENTE EM IMPLEMENTAÇÃO |
| M903 | Painéis e Android | Falha explícita se 028 não existe | CLIENTE EM IMPLEMENTAÇÃO |
| M904 | Painéis e Android | Sem botões de Pix ou fechamento | CLIENTE EM IMPLEMENTAÇÃO |
| M905 | Painéis e Android | Cache descarta troca de sessão | CLIENTE EM IMPLEMENTAÇÃO |
| M906 | Painéis e Android | API bloqueada sem sandbox flag | CLIENTE EM IMPLEMENTAÇÃO |
| M907 | Painéis e Android | Testes TypeScript malformados | CLIENTE EM IMPLEMENTAÇÃO |
| M908 | Painéis e Android | Compilação após quatro gates | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M909 | Painéis e Android | Testar no APK físico | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M910 | Painéis e Android | Registro de evidências visuais | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M911 | Governança de conclusão | Registrar todos os 160 controles | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M912 | Governança de conclusão | Vincular artefato CI ao SHA | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M913 | Governança de conclusão | Corrigir falhas em cada job | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M914 | Governança de conclusão | Auditar drift do schema | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M915 | Governança de conclusão | Não declarar tudo PASS por teste unitário | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M916 | Governança de conclusão | Sincronizar seguro por ff-only | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M917 | Governança de conclusão | Manter PR Draft | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M918 | Governança de conclusão | Sem merge para main | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M919 | Governança de conclusão | Homologar OCI antes do jurídico | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M920 | Governança de conclusão | Ativar dinheiro real só após autorizações | PENDENTE DE INTEGRAÇÃO OPERACIONAL |

## Critérios de conclusão técnica
1. Implementar e executar todos os fluxos reais em **sandbox** (revisão de inadimplência, saída, restituição simulada, fechamento e caixa), sem antecipar a etapa jurídica.
2. Preservar direitos e principal enquanto o pedido está pendente; a função de registro não executa bloqueio nem perda de lucro.
3. Completar testes OAuth/PIX sandbox multiempresa e caixa SaaS, com provas assinadas/idempotentes e lançamentos compensatórios.
4. Registrar e testar no aplicativo Android e staging Oracle OCI com logs protegidos, RLS, controle de custo, backup e restore.
5. Depois de todas as integrações comprovadas, abrir etapa jurídica para autorização de operação financeira real.
6. Sem alterações ao PostgreSQL Termux 5433, sem merge da PR #2; scripts locais continuam seguros 001–027 até aprovação específica de migração.

**A contagem de 160 é o total de tarefas rastreáveis, não 160 itens já concluídos.**
