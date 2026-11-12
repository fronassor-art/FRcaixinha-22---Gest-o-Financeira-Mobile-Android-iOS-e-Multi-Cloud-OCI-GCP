# FR Finance AI Studio — Passagem controlada GitHub → Termux → APK (M39020)

**Estado:** guia versionado, NÃO autorização para executar Git/SQL/FCM/Pix. Produção financeira, campanhas externas e cadastro real continuam **OFF**. A release é identificada pelo SHA de commit cujos workflows de CI foram concluídos com sucesso; **não** confiar apenas no nome da branch.

## 1. O que está preparado
- Contrato Técnico Mestre e Caderno Mestre atualizados: CTM-CRED-EX-01 a 06 / CM-CRED-EX-01.
- Autorização excepcional individual ou múltipla, com teto (máximo atual Price: R$ 50.000,00), validade, justificativa e idempotência.
- Campanhas com rascunho, publicação **internamente consultável**, cancelamento, resposta individual e simulação Price. Não é solicitação de desembolso.
- React/Capacitor Android com diagnóstico explícito do plugin push e preferências independentes PUSH/EMAIL/WHATSAPP/SMS.
- Adapters para FCM, Brevo e-mail, WhatsApp Cloud e Brevo SMS **sem transporte autorizado**; outbox BLOCKED_EXTERNAL.
- SQL 110 e 111 com 6 tabelas FORCE RLS e 5 gatilhos de integridade. São **candidatas**, não aplicadas no banco original.
- `.gitignore` protege o `android/app/google-services.json` local. Este arquivo não foi provisionado no GitHub.

## 2. Aceite antes de qualquer sincronização local
1. Identificar SHA completo do HEAD na branch `atualizacao-ai-studio-9b46a63187`.
2. Todos os workflows relevantes do **mesmo SHA** devem registrar `success`; verificar o job SQL 110/111 PostgreSQL 18, API FastAPI, regressões, Vite/Capacitor e build APK debug.
3. Reconciliar alteração do catálogo SQL e garantir que não existam outras modificações concorrentes.
4. Obter concordância do operador para atualizar os arquivos Git no Termux. **Esta documentação não executa nada.**

### Comandos de sincronização futura (SOMENTE APÓS ACEITE)
```bash
cd "$HOME/fr-finance"
git status --short
git branch --show-current
git fetch --no-tags origin atualizacao-ai-studio-9b46a63187
git merge --ff-only origin/atualizacao-ai-studio-9b46a63187
git rev-parse HEAD
# Substituir SHA_APROVADO pelo commit exato homologado no CI:
export AI_STUDIO_APPROVED_SHA=SHA_APROVADO
bash backend/scripts/frfinance_m39020_termux_preflight.sh
```
O preflight executa apenas verificação de repositório e leitura do PostgreSQL original; exige a senha `frc_ai_owner` digitada localmente, não enviada ao GitHub/ChatGPT.

## 3. Aplicação futura — exige autorização específica e independente
A aplicação das SQLs 110+111 NÃO é automática na sincronização Git. Apenas após análise do resultado do preflight, backup/restauro e aprovação da migração:
```bash
cd "$HOME/fr-finance"
export AI_STUDIO_APPROVED_SHA=SHA_APROVADO
export FR_FINANCE_M39020_APPLY_APPROVED=YES_AFTER_INDEPENDENT_REVIEW
export FR_FINANCE_M39020_RESTORE_TEST=YES
bash backend/scripts/frfinance_m39020_termux_apply_guarded.sh
```
O script:
- checa SHA, branch, árvore limpa e hashes do catálogo;
- confere banco `frcaixinha_aistudio_dev`/porta `5433`, papel `frc_ai_owner` e PostgreSQL 18;
- recusa estado parcial, cria backup privado fora do repositório, valida SHA-256 e **restaura em banco descartável** antes da aplicação;
- usa `psql --single-transaction` com `frfinance.m39020_migration_mode='LOCAL_AUTHORIZED'` para SQL 110 e 111, sem BEGIN/COMMIT internos;
- exige 6 tabelas RLS FORCE + 5 triggers ativados ao final;
- não habilita Pix, notificações externas ou produção.
Se houver falha, **parar**, manter o backup e enviar o relatório técnico sem senha. Não tentar aplicar os arquivos SQL isoladamente.

## 4. Preparação local do APK de homologação (após migração aprovada)
Em arquivo privado de ambiente do FastAPI, ativar `FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES`, mantendo `FRCAIXINHA_TEST_AUTH=1` e os demais gates locais anteriores. O backend exige `frc_ai_app@127.0.0.1:5433/frcaixinha_aistudio_dev`; produção é rejeitada.

Build Android de testes: `FRCAIXINHA_ANDROID_LOCAL_TEST=1` e `VITE_API_URL=http://127.0.0.1:8000` no **build debug**, seguido de `npm ci`, `npm run cap:build` e montagem do APK conforme o procedimento Android já homologado. Nunca usar Termux/loopback num release de produção.

Para testar a **permissão e registro FCM nativo**, o APK exige `VITE_FR_FINANCE_PUSH_DIAGNOSTIC=YES`, opt-in explícito do membro e a configuração privada `android/app/google-services.json` no projeto Android debug. Nenhum token é armazenado/enviado pela implementação atual. O plugin permite somente prova de capacidade do aparelho, não atesta entrega remota até o backend/provedor efetivamente homologados.

## 5. Testes funcionais planejados
1. Admin entra em sua caixinha; selecionar 1 e depois vários membros ativos.
2. Registrar tetos excepcionais válidos, justificar, verificar duplicação/idempotência e bloquear tenant alheio.
3. Criar rascunho, selecionar autorizações e publicar. Verificar ausência de Pix e lançamento financeiro.
4. Membro vê somente suas oportunidades, registra interesse ou recusa sem penalidades e realiza simulação Price.
5. Testar expiração, revogação, perfil MASTER, membro de outra caixinha e campanha cancelada.
6. Alterar preferências PUSH/EMAIL/WHATSAPP/SMS e conferir que nenhuma comunicação externa foi enviada.
7. No Android, fazer diagnóstico de permissão e registro local FCM **somente se houver configuração privada**, sem declarar push entregue.
8. Validar visualmente o APK debug com o operador. Publicação comercial segue bloqueada.

## 6. Checkpoints de saída
```
SQL_CATALOG=113_VERSIONADOS
LOCAL_110_111=NOT_APPLIED_UNTIL_OPERATOR_APPROVAL
RLS_EXPECTED=6_TABLES_FORCE
GUARDS_EXPECTED=5_TRIGGERS
PUSH_EXTERNAL=OFF
EMAIL_EXTERNAL=OFF
WHATSAPP_EXTERNAL=OFF
SMS_EXTERNAL=OFF
PIX_REAL=OFF
PRODUCTION_CREDIT=OFF
```
Os valores acima são **expectativas de homologação**, não resultados reais do banco Termux. Não marcar PASS de execução local sem evidência produzida pelo operador.
