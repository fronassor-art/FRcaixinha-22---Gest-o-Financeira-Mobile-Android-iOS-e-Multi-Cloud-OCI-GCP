# FR Caixinha AI Studio — Macropacote M921–M1080

**Data:** 04/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`. **PR:** #2 Draft. **Projeto:** FR Caixinha AI Studio Mobile, sem relação operacional com o repositório/banco da frente FRcaixinha 2.2 independente.

## Checkpoints
- M600, último comprovado sincronizado em Termux: `6cf856ce3840f72760f4ce53e690f7712359d468`.
- M760, falha de excesso de pagamento corrigida por `0b960be04d67a1b1d2daab21c83db9e7ed890cbd`, CI #229 6/6 PASS.
- M920, migração 028 inicialmente com expressão SQL incompleta; reparada no commit `f6a1caf6b7f8f652f7c208ddeed05cb63d8fe2cc`, CI #231 **6/6 PASS**.
- Nova frente M921–M1080: resultado **pendente** até concluir GitHub Actions para o commit específico.

## Funcionalidade desenvolvida nesta etapa
1. **Migration 028 corrigida e protegida:** tamanho, quantidade de statements, regex completo, RLS, idempotência e função SQL com controle de contexto verificados em CI.
2. **FastAPI:** GET `.../member-lifecycle/capabilities` informa a existência real da tabela e função; POST de homologação nunca é indicado como disponível sem schema instalado, flag explícita e ambiente fora de produção.
3. **Painel Android:** membro solicita saída sintética; administrador seleciona membro ativo para registrar revisão sintética; ambos dependem da capacidade declarada pelo servidor e confirmação do usuário, UUID de idempotência e sessão válida.
4. **Pendências de fechamento registradas:** GET `.../member-lifecycle/closing-gates` consulta quatro grupos: saídas, revisões, contribuições sem quitação e empréstimos não encerrados. **Nunca** retorna fechamento, rateio ou Pix autorizados.
5. **Testes:** centenas de cenários parametrizados em Python/TypeScript, APIs com perfis, servidor sem migration, fronteiras de sessão; laboratório PostgreSQL real descartável com dois tenants, fila RLS e verificações de gate financeiro.
6. **Nenhuma migração Termux ou OCI:** a migração 028 existe apenas no repositório e nas transações CI de PostgreSQL 16/18. O comando local de migração permanece fechado em 001–027; não aplicá-lo sem autorização específica.

## Objetivo técnico, etapa jurídica e bloqueios
A codificação, instalação em homologação e testes OCI **não dependem de obter previamente parecer jurídico**. A ativação financeira comercial é outra fase. A ausência de parecer não justifica deixar motor sem implementação e teste, mas os testes sintéticos não autorizam dinheiro real.

Nenhuma chamada Mercado Pago, Pix real, alteração automática de membership, confiscos, mudanças de saldo, fechamento ou liquidação ocorreu nesta etapa. Não se devem apresentar os valores registrados como saldo de caixa bancário conciliado.

## Matriz de 160 tarefas M921–M1080

`CÓDIGO/TESTE NESTE PACOTE` indica cobertura de código criada que ainda dependerá da CI final para ser homologada. `INTEGRAÇÃO OPERACIONAL PENDENTE` significa que a funcionalidade completa não foi entregue e não deve ser marcada como PASS. O total de 160 refere-se a controles rastreados, não a funcionalidades concluídas.

| ID | Frente | Controle | Estado |
|---|---|---|---|
| M921 | Migração e integridade SQL | Eliminar duplicação na migration 028 | CÓDIGO/TESTE NESTE PACOTE |
| M922 | Migração e integridade SQL | Validar fechamento da cláusula de regex | CÓDIGO/TESTE NESTE PACOTE |
| M923 | Migração e integridade SQL | Restringir comprimento da versão documental | CÓDIGO/TESTE NESTE PACOTE |
| M924 | Migração e integridade SQL | Uma tabela de solicitações por tenant/ciclo | CÓDIGO/TESTE NESTE PACOTE |
| M925 | Migração e integridade SQL | Uma função definer para submissão sandbox | CÓDIGO/TESTE NESTE PACOTE |
| M926 | Migração e integridade SQL | Dois índices para fila e histórico | CÓDIGO/TESTE NESTE PACOTE |
| M927 | Migração e integridade SQL | Úndice único para pendência por membro/tipo | CÓDIGO/TESTE NESTE PACOTE |
| M928 | Migração e integridade SQL | RLS habilitada e forçada | CÓDIGO/TESTE NESTE PACOTE |
| M929 | Migração e integridade SQL | Nenhum DML app direto em solicitações | CÓDIGO/TESTE NESTE PACOTE |
| M930 | Migração e integridade SQL | Termux 5433 permanece sem migração 028 | CÓDIGO/TESTE NESTE PACOTE |
| M931 | Controle de identidade | Sessão obrigatória para consulta | CÓDIGO/TESTE NESTE PACOTE |
| M932 | Controle de identidade | Master não acessa fila de caixinha | CÓDIGO/TESTE NESTE PACOTE |
| M933 | Controle de identidade | Membro consulta somente próprios pedidos | CÓDIGO/TESTE NESTE PACOTE |
| M934 | Controle de identidade | Administrador consulta fila do próprio tenant | CÓDIGO/TESTE NESTE PACOTE |
| M935 | Controle de identidade | Membro não acessa revisão administrativa | CÓDIGO/TESTE NESTE PACOTE |
| M936 | Controle de identidade | Administrador não forja saída de membro | CÓDIGO/TESTE NESTE PACOTE |
| M937 | Controle de identidade | Vínculo ativo exigido para saída | CÓDIGO/TESTE NESTE PACOTE |
| M938 | Controle de identidade | Vínculo membro exige mesmo tenant | CÓDIGO/TESTE NESTE PACOTE |
| M939 | Controle de identidade | Ciclo pertence ao tenant | CÓDIGO/TESTE NESTE PACOTE |
| M940 | Controle de identidade | Status do membro nunca alterado no pedido | CÓDIGO/TESTE NESTE PACOTE |
| M941 | Registro e idempotência | UUID idempotente por pedido | CÓDIGO/TESTE NESTE PACOTE |
| M942 | Registro e idempotência | Identificador de solicitação auditável | CÓDIGO/TESTE NESTE PACOTE |
| M943 | Registro e idempotência | Reenvio com mesma chave retorna mesmo pedido | CÓDIGO/TESTE NESTE PACOTE |
| M944 | Registro e idempotência | Nova chave não duplica uma pendência | CÓDIGO/TESTE NESTE PACOTE |
| M945 | Registro e idempotência | Revisão separada de saída voluntária | CÓDIGO/TESTE NESTE PACOTE |
| M946 | Registro e idempotência | Política de referência conservada | CÓDIGO/TESTE NESTE PACOTE |
| M947 | Registro e idempotência | Política divergente rejeitada | CÓDIGO/TESTE NESTE PACOTE |
| M948 | Registro e idempotência | Ator divergente rejeitado | CÓDIGO/TESTE NESTE PACOTE |
| M949 | Registro e idempotência | Data de criação preservada | CÓDIGO/TESTE NESTE PACOTE |
| M950 | Registro e idempotência | Sem atualização ou exclusão via app | CÓDIGO/TESTE NESTE PACOTE |
| M951 | Gate de execução sandbox | POST desabilitado por padrão | CÓDIGO/TESTE NESTE PACOTE |
| M952 | Gate de execução sandbox | POST desabilitado em produção | CÓDIGO/TESTE NESTE PACOTE |
| M953 | Gate de execução sandbox | Flag explícita para sandbox | CÓDIGO/TESTE NESTE PACOTE |
| M954 | Gate de execução sandbox | Schema 028 detectado antes do botão | CÓDIGO/TESTE NESTE PACOTE |
| M955 | Gate de execução sandbox | Função SQL detectada antes do botão | CÓDIGO/TESTE NESTE PACOTE |
| M956 | Gate de execução sandbox | Role do cliente não decide autorização do SQL | CÓDIGO/TESTE NESTE PACOTE |
| M957 | Gate de execução sandbox | Capacidade do membro sem revisão admin | CÓDIGO/TESTE NESTE PACOTE |
| M958 | Gate de execução sandbox | Capacidade do admin sem saída alheia | CÓDIGO/TESTE NESTE PACOTE |
| M959 | Gate de execução sandbox | Falha de SQL dá erro explícito | CÓDIGO/TESTE NESTE PACOTE |
| M960 | Gate de execução sandbox | Nenhum Pix/transferência habilitado | CÓDIGO/TESTE NESTE PACOTE |
| M961 | Interface e sessão | Painel de fila no app | CÓDIGO/TESTE NESTE PACOTE |
| M962 | Interface e sessão | Painel em perfil de membro | CÓDIGO/TESTE NESTE PACOTE |
| M963 | Interface e sessão | Painel em perfil admin | CÓDIGO/TESTE NESTE PACOTE |
| M964 | Interface e sessão | Lista de membros do próprio tenant | CÓDIGO/TESTE NESTE PACOTE |
| M965 | Interface e sessão | Seleção obrigatória de membro para revisão | CÓDIGO/TESTE NESTE PACOTE |
| M966 | Interface e sessão | Confirmação explícita de teste | CÓDIGO/TESTE NESTE PACOTE |
| M967 | Interface e sessão | Chave UUID segura e reutilizável na tentativa | CÓDIGO/TESTE NESTE PACOTE |
| M968 | Interface e sessão | Repetição após erro não cria nova obrigação | CÓDIGO/TESTE NESTE PACOTE |
| M969 | Interface e sessão | Resultado antigo é descartado após troca de sessão | CÓDIGO/TESTE NESTE PACOTE |
| M970 | Interface e sessão | Sem cache financeiro em localStorage | CÓDIGO/TESTE NESTE PACOTE |
| M971 | Prévia de fechamento | Contar saídas pendentes | CÓDIGO/TESTE NESTE PACOTE |
| M972 | Prévia de fechamento | Contar revisões de inadimplência | CÓDIGO/TESTE NESTE PACOTE |
| M973 | Prévia de fechamento | Contar contribuições sem quitação registrada | CÓDIGO/TESTE NESTE PACOTE |
| M974 | Prévia de fechamento | Contar empréstimos não encerrados | CÓDIGO/TESTE NESTE PACOTE |
| M975 | Prévia de fechamento | Consultar apenas no perfil admin | CÓDIGO/TESTE NESTE PACOTE |
| M976 | Prévia de fechamento | Sem comprovação bancária alegada | CÓDIGO/TESTE NESTE PACOTE |
| M977 | Prévia de fechamento | Nunca autorizar fechamento pela prévia | CÓDIGO/TESTE NESTE PACOTE |
| M978 | Prévia de fechamento | Nunca autorizar rateio pela prévia | CÓDIGO/TESTE NESTE PACOTE |
| M979 | Prévia de fechamento | Nunca autorizar pagamento pela prévia | CÓDIGO/TESTE NESTE PACOTE |
| M980 | Prévia de fechamento | Falhar fechado sem migração 028 | CÓDIGO/TESTE NESTE PACOTE |
| M981 | Contrato de dados e parser | Parser fechado de capacidades | CÓDIGO/TESTE NESTE PACOTE |
| M982 | Contrato de dados e parser | Parser fechado de solicitação | CÓDIGO/TESTE NESTE PACOTE |
| M983 | Contrato de dados e parser | Parser fechado da fila | CÓDIGO/TESTE NESTE PACOTE |
| M984 | Contrato de dados e parser | Parser fechado de pendências de fechamento | CÓDIGO/TESTE NESTE PACOTE |
| M985 | Contrato de dados e parser | Rejeitar campos adicionais | CÓDIGO/TESTE NESTE PACOTE |
| M986 | Contrato de dados e parser | Rejeitar tenant divergente | CÓDIGO/TESTE NESTE PACOTE |
| M987 | Contrato de dados e parser | Rejeitar estados como LIQUIDADO | CÓDIGO/TESTE NESTE PACOTE |
| M988 | Contrato de dados e parser | Rejeitar booleanos financeiros verdadeiros | CÓDIGO/TESTE NESTE PACOTE |
| M989 | Contrato de dados e parser | Rejeitar valores numéricos negativos | CÓDIGO/TESTE NESTE PACOTE |
| M990 | Contrato de dados e parser | Rejeitar duplicação de IDs na fila | CÓDIGO/TESTE NESTE PACOTE |
| M991 | Bateria PostgreSQL | PostgreSQL 16 descartável | CÓDIGO/TESTE NESTE PACOTE |
| M992 | Bateria PostgreSQL | PostgreSQL 18 descartável | CÓDIGO/TESTE NESTE PACOTE |
| M993 | Bateria PostgreSQL | Migrações até 028 em transação CI | CÓDIGO/TESTE NESTE PACOTE |
| M994 | Bateria PostgreSQL | Identidade sintética de dois administradores | CÓDIGO/TESTE NESTE PACOTE |
| M995 | Bateria PostgreSQL | Membros fictícios de dois tenants | CÓDIGO/TESTE NESTE PACOTE |
| M996 | Bateria PostgreSQL | Teste de RLS membro | CÓDIGO/TESTE NESTE PACOTE |
| M997 | Bateria PostgreSQL | Teste de RLS administrador | CÓDIGO/TESTE NESTE PACOTE |
| M998 | Bateria PostgreSQL | Teste de Master negado | CÓDIGO/TESTE NESTE PACOTE |
| M999 | Bateria PostgreSQL | Teste de escrita direta negada | CÓDIGO/TESTE NESTE PACOTE |
| M1000 | Bateria PostgreSQL | Limpeza das entidades fictícias | CÓDIGO/TESTE NESTE PACOTE |
| M1001 | Inadimplência operacional | Consolidar três competências consecutivas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1002 | Inadimplência operacional | Separar atraso de 90 dias | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1003 | Inadimplência operacional | Regularização tardia imutável | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1004 | Inadimplência operacional | Avaliar elegibilidade por ciclo | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1005 | Inadimplência operacional | Documentar ciência do membro | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1006 | Inadimplência operacional | Revisar contestações | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1007 | Inadimplência operacional | Persistir decisão autorizada | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1008 | Inadimplência operacional | Bloquear novas operações conforme contrato | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1009 | Inadimplência operacional | Preservar principal e histórico | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1010 | Inadimplência operacional | Automatizar reativação conforme cláusula | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1011 | Saída e restituição | Pedido com prova de autoria | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1012 | Saída e restituição | Versão contratual de adesão | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1013 | Saída e restituição | Extrato consolidado no desligamento | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1014 | Saída e restituição | Dívidas comprovadas separadas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1015 | Saída e restituição | Principal reconciliado a restituir | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1016 | Saída e restituição | Lucro adquirido preservado | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1017 | Saída e restituição | Trilha de aprovação independente | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1018 | Saída e restituição | Gerar comprovante de decisão | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1019 | Saída e restituição | Simular Pix de restituição sandbox | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1020 | Saída e restituição | Liquidação real só com autorização | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1021 | Motor de lucro e rateio | Lucro realizado menos despesas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1022 | Motor de lucro e rateio | Capital de cota fora do lucro | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1023 | Motor de lucro e rateio | Reversões e perdas documentadas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1024 | Motor de lucro e rateio | Percentuais aceitos por tenant e ciclo | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1025 | Motor de lucro e rateio | Caixinha inaugural 15/85 | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1026 | Motor de lucro e rateio | Capital-Dias com fuso Belém | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1027 | Motor de lucro e rateio | Exclusão de lucro somente após revisão | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1028 | Motor de lucro e rateio | Peso de desligado regular preservado | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1029 | Motor de lucro e rateio | Rateio por maiores restos | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1030 | Motor de lucro e rateio | Carteira técnica segregada | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1031 | Caixas e reconciliação | Conta da plataforma separada | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1032 | Caixas e reconciliação | Receita de licença SaaS Master | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1033 | Caixas e reconciliação | Conta da caixinha por tenant | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1034 | Caixas e reconciliação | Conta de capital dos membros | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1035 | Caixas e reconciliação | Conta de receita de juros | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1036 | Caixas e reconciliação | Contas de despesas/perdas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1037 | Caixas e reconciliação | Ledger de partidas dobradas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1038 | Caixas e reconciliação | Provedor reconciliado com referência | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1039 | Caixas e reconciliação | Estornos idempotentes | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1040 | Caixas e reconciliação | Saldo líquido após conciliação real | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1041 | Mercado Pago sandbox | OAuth Connect individual por caixinha | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1042 | Mercado Pago sandbox | Token do Master apenas no backend | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1043 | Mercado Pago sandbox | Credenciais de teste isoladas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1044 | Mercado Pago sandbox | Intenção Pix com idempotência | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1045 | Mercado Pago sandbox | QR Pix temporário | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1046 | Mercado Pago sandbox | GET status autoritativo | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1047 | Mercado Pago sandbox | Webhook autenticado | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1048 | Mercado Pago sandbox | Evento repetido sem dupla baixa | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1049 | Mercado Pago sandbox | Reembolso e chargeback de testes | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1050 | Mercado Pago sandbox | Nenhum dinheiro real em CI | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1051 | Oracle OCI staging | Infraestrutura OCI segregada | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1052 | Oracle OCI staging | PostgreSQL ou banco compatível em staging | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1053 | Oracle OCI staging | API FastAPI com TLS | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1054 | Oracle OCI staging | Gestão de segredos e rotação | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1055 | Oracle OCI staging | Rede privada e limites de tráfego | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1056 | Oracle OCI staging | Backup cifrado | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1057 | Oracle OCI staging | Restauração ensaiada | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1058 | Oracle OCI staging | Fila e recuperação de webhooks | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1059 | Oracle OCI staging | Teste de concorrência e carga | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1060 | Oracle OCI staging | Teste Android conectado ao OCI | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1061 | Qualidade de entrega | Executar contrato do mestre do AI Studio | CÓDIGO/TESTE NESTE PACOTE |
| M1062 | Qualidade de entrega | Validar schema sem truncamento | CÓDIGO/TESTE NESTE PACOTE |
| M1063 | Qualidade de entrega | Rodar testes unitários API | CÓDIGO/TESTE NESTE PACOTE |
| M1064 | Qualidade de entrega | Rodar testes de TypeScript | CÓDIGO/TESTE NESTE PACOTE |
| M1065 | Qualidade de entrega | Rodar CI PostgreSQL 16 | CÓDIGO/TESTE NESTE PACOTE |
| M1066 | Qualidade de entrega | Rodar CI PostgreSQL 18 | CÓDIGO/TESTE NESTE PACOTE |
| M1067 | Qualidade de entrega | Compilar APK só após gates | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1068 | Qualidade de entrega | Confirmar SHA exato no GitHub | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1069 | Qualidade de entrega | Sincronizar Termux sem sobrescrever mudanças | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1070 | Qualidade de entrega | Capturar homologação visual no aparelho | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1071 | Governança e ativação | PR #2 permanece Draft | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1072 | Governança e ativação | Sem merge automático em main | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1073 | Governança e ativação | Sem migração automática no 5433 | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1074 | Governança e ativação | Sem dinheiro real até autorização | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1075 | Governança e ativação | Desenvolvimento independente da etapa jurídica | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1076 | Governança e ativação | Homologação OCI anterior à análise jurídica | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1077 | Governança e ativação | Rastrear todas as 147 cláusulas | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1078 | Governança e ativação | Não declarar concluído sem prova de ponta a ponta | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1079 | Governança e ativação | Documentar pendências de integração | INTEGRAÇÃO OPERACIONAL PENDENTE |
| M1080 | Governança e ativação | Planejar ativação comercial pós-aprovação | INTEGRAÇÃO OPERACIONAL PENDENTE |

## Próximos gates de conclusão real
- Finalizar operação de review e aprovação documentada de saídas/inadimplência, com estado imutável, contestação e retenção de direitos.
- Implementar conciliação Mercado Pago Connect **sandbox** segregada em Master e cada administrador, webhooks, estornos, chargebacks e eventos idempotentes.
- Integrar fechamento com valor líquido, Capital-Dias V2, custos, pesos e restituições; publicar comprovantes e testes de contas.
- Subir staging OCI isolado e homologar API, banco, filas, backups/restore, observabilidade e APK Android com dados simulados.
- Só promover checkpoint ao Termux e APK quando CI do SHA exato estiver 6/6 PASS; PR permanece Draft, nunca merge sem auditoria completa.

**Nota:** rastrear todos os requisitos do Documento Mestre, sem inferir parâmetros do outro projeto FRcaixinha 2.2. O fechamento real permanece desabilitado enquanto o desenvolvimento técnico prossegue.
