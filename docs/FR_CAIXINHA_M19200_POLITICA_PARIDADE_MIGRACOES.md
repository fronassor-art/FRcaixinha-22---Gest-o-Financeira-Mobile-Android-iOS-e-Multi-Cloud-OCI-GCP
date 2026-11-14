# FR Caixinha AI Studio — M19200: contrato de paridade de migrações

## Evidência de homologação no Termux
Em 05/11/2026, o usuário confirmou o APK 36d3c0b nos três papéis Master/Administrador/Membro. Aviso de sessão, aviso de teste, contador de não lidas, marcação como lida e histórico persistido foram vistos. Não considerar ainda testados: isolamento com dois usuários distintos, paginação >20 mensagens, paradas/reinícios da API ou avisos externos.
O PostgreSQL 18.6 exclusivo na porta 5433 chegou a 34 tabelas após a migração local 031, com RLS e permissões verificadas. A API local está READY, PID 5455 na última saída. Isso não prova histórico individual de aplicação de todos os SQL 001–027.

## Regra operacional obrigatória
1. Nenhuma função nova que dependa de schema PostgreSQL pode ser classificada como homologada no APK sem migração incremental própria, testes em PostgreSQL descartável, backup antes de aplicar, verificação RLS/roles e evidência do banco Termux.
2. Toda migração SQL precisa estar registrada em backend/migration_catalog_ai_studio.json com origem qualificada (família e número), classificação e hash SHA do blob Git. A CI agora falha quando há arquivo SQL desconhecido, alterado sem registro ou instalador local que cite caminhos ci_migrations/staging_migrations.
3. Sincronizar código via Git não aplica DDL. O comando local de aplicação deve ser entregue após CI, ter guarda exata no banco frcaixinha_aistudio_dev e porta 5433, rollback transacional, backup criptografado verificado, confirmação explícita e leitura pós-aplicação.
4. Nenhum script original de ci_migrations ou staging_migrations deve ser executado no Termux. O local exige versões próprias revisadas e testadas; a CI descartável não é licença para habilitar pagamento, conciliação, Pix, webhooks, ledgers ou notificações externas reais.
5. Se a migração local falhar, o pacote não é homologado e não se avança com teste físico dependente dela. Contratos bloqueados são relatados nominalmente, não ocultados ou marcados como PASS.

## Matriz abrangente de 46 scripts SQL

| Namespace | Arquivos | Estado no Termux | Próxima ação |
| --- | --- | --- | --- |
| migrations:001–027 | 27 | base estrutural presente, histórico SQL por arquivo não atestado | inventário de objetos e metadados |
| migrations:028–030 | 3 | código originalmente só CI; sem implantação local comprovada | portar fluxo de saída/inadimplência sem efeito patrimonial e ensaiar ciclo completo |
| migrations:031 | 1 | aplicada em Termux; caixa interna testada nos três papéis | concluir isolamento múltiplos usuários e reinício |
| ci_migrations:031–037 | 7 | fixtures e provas descartáveis não destinadas à implantação local | manter exclusivamente em CI; não criar dados fictícios no banco permanente por obrigação de numeração |
| staging_migrations:034–041 | 8 | SQL com guardas explícitas OCI/CI, não instalável em Termux | desenhar equivalentes locais homologáveis por módulo com flags financeiras false |

## Dependências de cada staging migration
staging:034 conexão seller e webhook assinado (requer gestão segura de identidade, sem credenciais reais no Termux).
staging:035 operações PIX, evidências de liquidação e payouts (somente modelo sintético local, sem efetuar transferências).
staging:036 inbox Orders assinadas (depende de 034).
staging:037 vínculos entre Orders e operações sintéticas (depende de 034–036).
staging:038 reserva/controle de idempotência e integridade entre tenants (depende de 034–037).
staging:039 holds de conciliação como evidência não verificada (depende de 038).
staging:040 auditoria append-only de incidentes (depende de 039).
staging:041 inbox/outbox sintética de notificação; a M031 local já fornece apenas inbox de sessão e selftest. Não presumir equivalência da outbox de eventos financeiros.

## Auditoria sem DDL no Termux
Após CI aprovada e sincronização do commit:
AI_STUDIO_APPROVED_SHA=COMMIT_SHA40 python3 backend/scripts/aistudio_migration_inventory.py local-readonly
Solicita senha PostgreSQL por prompt oculto; verifica identidade do cluster, tabelas, funções e RLS. Não cria, atualiza ou remove registros. Somente compartilhe os marcadores, nunca senhas ou api.env.

## Definição de pronto para novos macropacotes
Cada pacote de API/UI com persistência inclui SQL local versionado e catálogo atualizado, teste em PG16/18, script de preflight/apply/verify, backup age, migração executada no Termux e verificações runtime. APK gerado no mesmo commit e instalado apenas após migração homologada. Dinheiro real, OCI e canais externos continuam desativados até aprovação independente.

PR #2 continua Draft e sem merge; nenhuma migração local foi executada pelos commits de documentação/governança M19200.
