# FR Finance — Macropacote M38800–M38959 (160 controles planejados)

**Repositório único:** `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP` · branch `atualizacao-ai-studio-9b46a63187` · Termux `$HOME/fr-finance` · PostgreSQL 18 existente `127.0.0.1:5433/frcaixinha_aistudio_dev` · FastAPI existente `127.0.0.1:8000`.

**Regras fixas:** não criar/clonar outro repositório, worktree, diretório do projeto, PostgreSQL, FastAPI ou banco; não fazer `initdb` ou `createdb`; não restaurar nem executar migrações SQL por engano; sempre consultar estado do PostgreSQL/FastAPI antes de diagnosticar problemas após o Android encerrar o Termux. O FR Caixinha 2.2 não participa deste trabalho.

**Evidência real M38790:** schema local 043/044 `COMPATIBLE_OBSERVED` (10 flags TRUE), `MIGRATION_PROVENANCE=NOT_ATTESTED`. Isso não autoriza reaplicar as migrações e tampouco equivale a E2E de produção.

**Estado da entrega atual:** os códigos M38800 de sondagem de serviços existentes, M38801 de proteção do launcher atual, M38802 de URLs do mesmo DB, M38803 de identificação de fechamento e M38804 de gate de notificações foram implementados na branch, com regressões sintéticas e sem migração SQL. As tarefas abaixo são um **plano auditável de 160 controles**: os controles 38800–38819 representam a frente operacional deste pacote e os demais continuam como frente de desenvolvimento e validação; não são 160 implementações completas ou aprovações de produção.

## 16 frentes de 10 tarefas

### Frente 01 — Serviços existentes PG18 e FastAPI

- **M38800** [implementação operacional/CI nesta entrega]: Validar worktree original antes de sondar serviços.
- **M38801** [implementação operacional/CI nesta entrega]: Consultar estado do PG18 na porta 5433.
- **M38802** [implementação operacional/CI nesta entrega]: Consultar GET de saúde da FastAPI existente na porta 8000.
- **M38803** [implementação operacional/CI nesta entrega]: Conferir identificação FR Finance na resposta HTTP.
- **M38804** [implementação operacional/CI nesta entrega]: Consultar readiness local somente quando PG estiver disponível.
- **M38805** [implementação operacional/CI nesta entrega]: Bloquear porta 8000 atendida por outro aplicativo.
- **M38806** [implementação operacional/CI nesta entrega]: Limitar tamanho de resposta HTTP da sondagem.
- **M38807** [implementação operacional/CI nesta entrega]: Impedir redirecionamentos e proxies durante a sondagem.
- **M38808** [implementação operacional/CI nesta entrega]: Desconsiderar variáveis PG* herdadas.
- **M38809** [implementação operacional/CI nesta entrega]: Executar verificação offline sem tocar no banco.

### Frente 02 — Inicializador único e URLs do banco

- **M38810** [implementação operacional/CI nesta entrega]: Confirmar launcher existente no mesmo worktree.
- **M38811** [implementação operacional/CI nesta entrega]: Conferir branch e remoto via isolamento M38794.
- **M38812** [implementação operacional/CI nesta entrega]: Exigir PG original ativo antes de executar FastAPI.
- **M38813** [implementação operacional/CI nesta entrega]: Exigir 5433 aceitando conexões.
- **M38814** [implementação operacional/CI nesta entrega]: Recusar iniciar segunda instância na porta 8000.
- **M38815** [implementação operacional/CI nesta entrega]: Reutilizar arquivo api.env existente sem criar diretórios.
- **M38816** [implementação operacional/CI nesta entrega]: Manter validação de permissões 0600 do arquivo local.
- **M38817** [implementação operacional/CI nesta entrega]: Validar as três URLs de papéis segregados do mesmo banco.
- **M38818** [implementação operacional/CI nesta entrega]: Rejeitar parâmetros query/fragment e redirecionamento de banco.
- **M38819** [implementação operacional/CI nesta entrega]: Manter ambiente de homologação e produção bloqueada.

### Frente 03 — Estruturas financeiras SQL 043/044

- **M38820** [pendente de integração ou homologação]: Preservar identificação exata da base original.
- **M38821** [pendente de integração ou homologação]: Conservar proveniência de migração como não atestada.
- **M38822** [pendente de integração ou homologação]: Verificar constraints de piso R$150 por ciclo.
- **M38823** [pendente de integração ou homologação]: Verificar quota mínima R$150 por membro.
- **M38824** [pendente de integração ou homologação]: Verificar ausência de default legado R$100.
- **M38825** [pendente de integração ou homologação]: Verificar wrapper protegido de alteração de preço.
- **M38826** [pendente de integração ou homologação]: Verificar bloqueio de função legada pública.
- **M38827** [pendente de integração ou homologação]: Verificar auditoria RLS na abertura.
- **M38828** [pendente de integração ou homologação]: Verificar triggers de imutabilidade e idempotência.
- **M38829** [pendente de integração ou homologação]: Não reaplicar SQL já compatível sem divergência observada.

### Frente 04 — Ciclo e contribuições

- **M38830** [pendente de integração ou homologação]: Preço definido pelo administrador na abertura.
- **M38831** [pendente de integração ou homologação]: Validar preço em centavos sem float.
- **M38832** [pendente de integração ou homologação]: Preservar valores históricos inferiores ao piso.
- **M38833** [pendente de integração ou homologação]: Rejeitar criação de novas obrigações abaixo de R$150.
- **M38834** [pendente de integração ou homologação]: Isolar tenant e ano do ciclo.
- **M38835** [pendente de integração ou homologação]: Registrar justificativa da alteração de preço.
- **M38836** [pendente de integração ou homologação]: Exigir idempotência em nova abertura.
- **M38837** [pendente de integração ou homologação]: Proibir reprecificação de obrigações passadas.
- **M38838** [pendente de integração ou homologação]: Exigir autorização administrativa comprovada.
- **M38839** [pendente de integração ou homologação]: Homologar fluxos Android e FastAPI existentes.

### Frente 05 — Identidade e autenticação

- **M38840** [pendente de integração ou homologação]: Validar sessão autenticada.
- **M38841** [pendente de integração ou homologação]: Exigir escopo de tenant.
- **M38842** [pendente de integração ou homologação]: Verificar papéis não superusuários.
- **M38843** [pendente de integração ou homologação]: Separar credenciais app/auth/verifier.
- **M38844** [pendente de integração ou homologação]: Bloquear vazamento de hash de senha.
- **M38845** [pendente de integração ou homologação]: Limitar tentativas de autenticação.
- **M38846** [pendente de integração ou homologação]: Validar prazo e uso único de desafios.
- **M38847** [pendente de integração ou homologação]: Rejeitar reutilização de tokens.
- **M38848** [pendente de integração ou homologação]: Revalidar sessão pós-reinicialização da API.
- **M38849** [pendente de integração ou homologação]: Comprovar isolamento de usuário entre caixinhas.

### Frente 06 — Admissão de administradores e membros

- **M38850** [pendente de integração ou homologação]: Verificar convite existente.
- **M38851** [pendente de integração ou homologação]: Validar consentimento explícito.
- **M38852** [pendente de integração ou homologação]: Confirmar vínculo correto com a caixinha.
- **M38853** [pendente de integração ou homologação]: Validar conta de destinatário.
- **M38854** [pendente de integração ou homologação]: Impedir admissão duplicada.
- **M38855** [pendente de integração ou homologação]: Verificar aceite do contrato por versão.
- **M38856** [pendente de integração ou homologação]: Registrar rejeição com trilha auditável.
- **M38857** [pendente de integração ou homologação]: Evitar ativação real sem infraestrutura homologada.
- **M38858** [pendente de integração ou homologação]: Testar cancelamento seguro do convite.
- **M38859** [pendente de integração ou homologação]: Criar matriz de homologação de admissão no Android.

### Frente 07 — Fechamento anual e rateio

- **M38860** [pendente de integração ou homologação]: Apurar somente lucro real validado.
- **M38861** [pendente de integração ou homologação]: Separar capital principal de lucro.
- **M38862** [pendente de integração ou homologação]: Separar receitas SaaS do Caixa Master.
- **M38863** [pendente de integração ou homologação]: Calcular 15% para administrador.
- **M38864** [pendente de integração ou homologação]: Calcular 85% para membros elegíveis.
- **M38865** [pendente de integração ou homologação]: Definir arredondamento de centavos.
- **M38866** [pendente de integração ou homologação]: Exigir provas bancárias de liquidação.
- **M38867** [pendente de integração ou homologação]: Bloquear rateio para inadimplência de 90 dias.
- **M38868** [pendente de integração ou homologação]: Preservar restituição de capital conforme contrato.
- **M38869** [pendente de integração ou homologação]: Manter fechamento real indisponível sem autorização.

### Frente 08 — Notificações internas

- **M38870** [pendente de integração ou homologação]: Verificar API de inbox original.
- **M38871** [pendente de integração ou homologação]: Exigir RLS e escopo de destinatário.
- **M38872** [pendente de integração ou homologação]: Conferir URL de banco sem parâmetros externos.
- **M38873** [pendente de integração ou homologação]: Conferir assinatura HMAC do cursor.
- **M38874** [pendente de integração ou homologação]: Evitar vazamento de notificações entre tenants.
- **M38875** [pendente de integração ou homologação]: Tratar paginação idempotente.
- **M38876** [pendente de integração ou homologação]: Verificar marcação de leitura segura.
- **M38877** [pendente de integração ou homologação]: Confirmar schema de inbox sem criar outro banco.
- **M38878** [pendente de integração ou homologação]: Repetir testes após reinício do Termux.
- **M38879** [pendente de integração ou homologação]: Não ativar push externo sem integração.

### Frente 09 — Brevo e mensagens de e-mail

- **M38880** [pendente de integração ou homologação]: Conferir origem autenticada do domínio.
- **M38881** [pendente de integração ou homologação]: Revalidar DKIM1 e DKIM2 públicos.
- **M38882** [pendente de integração ou homologação]: Revalidar SPF limitado e DMARC.
- **M38883** [pendente de integração ou homologação]: Diferenciar DNS observado de aprovação Brevo.
- **M38884** [pendente de integração ou homologação]: Verificar SMTP STARTTLS sem envio real.
- **M38885** [pendente de integração ou homologação]: Validar remetente de contato/suporte.
- **M38886** [pendente de integração ou homologação]: Impedir envio de mensagens de teste a membros.
- **M38887** [pendente de integração ou homologação]: Segregar notificações internas e externas.
- **M38888** [pendente de integração ou homologação]: Planejar fluxo de reenvio e cotas.
- **M38889** [pendente de integração ou homologação]: Liberar envio real somente com evidências.

### Frente 10 — Mercado Pago OAuth Connect

- **M38890** [pendente de integração ou homologação]: Conferir tenant da conta conectada.
- **M38891** [pendente de integração ou homologação]: Validar PKCE e state.
- **M38892** [pendente de integração ou homologação]: Limitar callback OAuth a URI autorizada.
- **M38893** [pendente de integração ou homologação]: Verificar refresh token cifrado.
- **M38894** [pendente de integração ou homologação]: Garantir separação de credenciais por tenant.
- **M38895** [pendente de integração ou homologação]: Validar escopos de OAuth comerciais.
- **M38896** [pendente de integração ou homologação]: Impedir troca de conta entre administradores.
- **M38897** [pendente de integração ou homologação]: Comprovar delegação e consentimento.
- **M38898** [pendente de integração ou homologação]: Revalidar expiração e revogação de sessão.
- **M38899** [pendente de integração ou homologação]: Não permitir operações reais sem habilitação.

### Frente 11 — Pix de entrada

- **M38900** [pendente de integração ou homologação]: Verificar cota e obrigação a cobrar.
- **M38901** [pendente de integração ou homologação]: Validar valor e competência.
- **M38902** [pendente de integração ou homologação]: Impedir duplicidade de cobrança.
- **M38903** [pendente de integração ou homologação]: Verificar assinatura de webhook.
- **M38904** [pendente de integração ou homologação]: Relacionar comprovante com destinatário.
- **M38905** [pendente de integração ou homologação]: Persistir evento em inbox idempotente.
- **M38906** [pendente de integração ou homologação]: Validar conciliação antes do crédito.
- **M38907** [pendente de integração ou homologação]: Tratar reembolso e reversão sem duplicar saldo.
- **M38908** [pendente de integração ou homologação]: Bloquear contabilização em sandbox.
- **M38909** [pendente de integração ou homologação]: Manter Pix real OFF até homologação.

### Frente 12 — Pix de saída

- **M38910** [pendente de integração ou homologação]: Exigir saldo comprovado.
- **M38911** [pendente de integração ou homologação]: Validar destinatário existente.
- **M38912** [pendente de integração ou homologação]: Exigir autorização administrativa.
- **M38913** [pendente de integração ou homologação]: Confirmar habilitação Money Out comercial.
- **M38914** [pendente de integração ou homologação]: Revalidar limites transacionais.
- **M38915** [pendente de integração ou homologação]: Exigir chave de idempotência por pagamento.
- **M38916** [pendente de integração ou homologação]: Registrar status intermediário sem falso sucesso.
- **M38917** [pendente de integração ou homologação]: Bloquear reenvio de operação pendente.
- **M38918** [pendente de integração ou homologação]: Conciliar retorno do PSP antes de encerrar.
- **M38919** [pendente de integração ou homologação]: Não permitir transferência real sem aprovação.

### Frente 13 — OCI staging e operação

- **M38920** [pendente de integração ou homologação]: Conferir região sa-saopaulo-1.
- **M38921** [pendente de integração ou homologação]: Verificar VM A1 observada sem prometer capacidade.
- **M38922** [pendente de integração ou homologação]: Revalidar rede VCN FR Finance.
- **M38923** [pendente de integração ou homologação]: Conferir subnet e security list.
- **M38924** [pendente de integração ou homologação]: Conferir IAM do compartimento staging.
- **M38925** [pendente de integração ou homologação]: Não provisionar nova instância pelo Termux.
- **M38926** [pendente de integração ou homologação]: Planejar DNS/HTTPS do serviço existente.
- **M38927** [pendente de integração ou homologação]: Proteger segredos no Vault planejado.
- **M38928** [pendente de integração ou homologação]: Preparar implantação somente após VM disponível.
- **M38929** [pendente de integração ou homologação]: Testar readiness remota sem Pix ativo.

### Frente 14 — Android e experiência móvel

- **M38930** [pendente de integração ou homologação]: Verificar login/logout em sessão local.
- **M38931** [pendente de integração ou homologação]: Validar fluxo de convite de admin.
- **M38932** [pendente de integração ou homologação]: Validar entrada de membro.
- **M38933** [pendente de integração ou homologação]: Verificar escolha de valor >= R$150.
- **M38934** [pendente de integração ou homologação]: Verificar inbox e notificações.
- **M38935** [pendente de integração ou homologação]: Confirmar telas de Pix em modo desativado.
- **M38936** [pendente de integração ou homologação]: Testar retomada após fechamento do Termux.
- **M38937** [pendente de integração ou homologação]: Validar erros 503 quando API indisponível.
- **M38938** [pendente de integração ou homologação]: Testar APK debug na mesma branch.
- **M38939** [pendente de integração ou homologação]: Preparar build release sem ativação real.

### Frente 15 — Segurança, auditoria e CI

- **M38940** [pendente de integração ou homologação]: Manter isolamento FR Finance vs FR 2.2.
- **M38941** [pendente de integração ou homologação]: Bloquear bases de dados paralelas.
- **M38942** [pendente de integração ou homologação]: Bloquear diretórios de trabalho paralelos.
- **M38943** [pendente de integração ou homologação]: Bloquear repositórios paralelos.
- **M38944** [pendente de integração ou homologação]: Bloquear segunda FastAPI.
- **M38945** [pendente de integração ou homologação]: Conferir ausência de migração SQL automática.
- **M38946** [pendente de integração ou homologação]: Executar regressões de mínimo e RLS.
- **M38947** [pendente de integração ou homologação]: Executar testes de falhas de conexão.
- **M38948** [pendente de integração ou homologação]: Preservar logs sem senhas.
- **M38949** [pendente de integração ou homologação]: Produzir evidências CI com distinção sintético/real.

### Frente 16 — Homologação, migração de código e entrega

- **M38950** [pendente de integração ou homologação]: Sincronizar GitHub por fast-forward no worktree original.
- **M38951** [pendente de integração ou homologação]: Confirmar commit esperado antes do teste.
- **M38952** [pendente de integração ou homologação]: Executar regressão direcionada.
- **M38953** [pendente de integração ou homologação]: Executar regressão completa no Termux.
- **M38954** [pendente de integração ou homologação]: Sondar PG e API reais antes de concluir.
- **M38955** [pendente de integração ou homologação]: Separar compatibilidade de schema de prova histórica.
- **M38956** [pendente de integração ou homologação]: Listar pendências de provedores externos.
- **M38957** [pendente de integração ou homologação]: Planejar migração SQL futura apenas quando necessária.
- **M38958** [pendente de integração ou homologação]: Não liberar produção antes de E2E completo.
- **M38959** [pendente de integração ou homologação]: Retomar próximo pacote a partir do retorno do Termux.

## Ordem de trabalho

1. Executar o diagnóstico somente leitura dos **dois serviços existentes** (M38800), identificar se a API ou o PostgreSQL foram simplesmente encerrados pelo Android e nunca criar substitutos.
2. Reutilizar exclusivamente `backend/scripts/run_termux_fastapi.sh` quando a FastAPI estiver parada. Esse script exige PostgreSQL original ativo e recusa iniciar uma segunda API na porta 8000. O PostgreSQL pode ser iniciado somente no PGDATA original, com protocolo separado, nunca por causa de testes offline.
3. Desenvolver offline na **mesma branch**, executar CI e migrar **código por `git fetch` + `git merge --ff-only`** para `$HOME/fr-finance`. Migração SQL é uma operação diferente: não executar 043/044 porque seus schemas já foram observados como compatíveis, apesar da proveniência histórica não comprovada. Qualquer mudança futura deve ter diferença comprovada, guarda do banco exato e autorização operacional específica.
4. Executar regressão direcionada e completa no Termux; retornar o relatório. Com o retorno, continuar a próxima frente de desenvolvimento sem refazer etapas aprovadas e sem exigir confirmação para correções de código/testes seguros.
5. Não afirmar prontidão de produção enquanto OCI, domínio/SMTP, OAuth, webhooks, Pix, ativação e testes E2E reais não forem atestados. Pix e ativação reais permanecem desligados.

## Evidência e limites

A inspeção M38800 usa `pg_isready` somente na porta 5433 e HTTP GET em `/api/health` e `/api/health/ready` somente em 127.0.0.1:8000. A resposta /health atesta identidade declarada da API e /ready atesta apenas homologação local, não identidade criptográfica do processo ou liberação de produção. Testes CI são sintéticos e não usam o banco do telefone.
