# FR Finance AI Studio — M27200–M27210, ponte offline de desafio e recibo

## Entrada e escopo
M27106: commit `2da38d9`, 114 testes locais aprovados, 91 SQL versionados.
Apenas a branch `atualizacao-ai-studio-9b46a63187`. Nenhuma integração
com o projeto separado FRcaixinha 2.2, nenhum banco novo, nenhuma migração.

## M27200 — preparar token sem vazar segredo
`backend/app/email_challenge_material.py` exige o preflight AES-GCM M27000,
lease SQL autenticada, escopo/contrato coerentes, caixinha e destinatário
válidos. Cria token aleatório com 48 bytes CSPRNG (384 bits), duração 60–900
segundos e digest SHA-256. O `repr` é sempre censurado. Os parâmetros
`issue_sql_parameters()` contêm **somente** evento, digest e TTL para a
função `invite_issue_ci_email_challenge` de M27100.

**Limite fundamental**: preparar token não significa persistir o desafio.
Primeiro a emissão precisa ser confirmada em transação atômica SQL. O token
deve ser entregue somente por um worker homologado **após** confirmação da
gravação. Não usar link ou credenciais reais nessa etapa.

## M27210 — correlação de recibo sintético
`backend/app/email_receipt_correlation.py` exige comprovante assinado
sintético M26200, identidade do evento M27000, integridade do envelope
AES-GCM, marcação inequívoca de não verificado e relógio controlado.
Classifica recebimento de teste SMTP como `CI_SMTP_ACCEPTED_NOT_DELIVERED`,
ou `CI_BOUNCE_QUARANTINE_REQUIRED`, sem registrar qualquer alteração.
Idempotência durável e antifraude continuam a cargo da função SQL M26300,
sempre com outbox e lease autenticados; ela não é invocada aqui.

**Atenção:** o recebimento pelo SMTP não é entrega na caixa postal; um
comprovante assinado fictício não confirma posse do endereço. Token consumido
em CI não autoriza ativar usuário, conta Master, aceite de contrato ou Pix.

## Testes e bloqueios permanentes
`backend/tests/test_m27200_email_bridge_ci.py` cobre TTL, entropia,
segredos fora de logs e parâmetros SQL, troca de caixinha, quarentena,
replay/correlação, bounce, tentativa de elevar estados de autorização,
expiração, destinatário adulterado e proibição de exposição por HTTP.
Executado no workflow de validação; não executa código de rede nem SQL.

## Prerequisitos para passar do CI à OCI
1. Verificar domínio do remetente (SPF/DKIM/DMARC), provedor, política de
   credenciais por Vault/IAM e consentimento contratual do provedor.
2. Integrar worker real com PostgreSQL OCI, lease atômica e proteção
   contra reenvio após ACK ambíguo; demonstrar rollback e RLS por tenant.
3. Capturar recibo do provedor com autenticação **real**, distinção entre
   aceite SMTP e entrega, e revogação/bounce de forma idempotente.
4. Confirmar posse de e-mail com token entregue, persistência e consumo
   único, transição de identidade sob RLS, proteção de tentativas, MFA
   dos administradores e aceite individual do contrato publicado.
5. Realizar auditoria OCI sem tocar banco Termux 5433 nem habilitar Pix.

`FR_FINANCE_PIX_REAL=DESATIVADO`. `LOCAL_SQL_APPLY=NONE`.
`EMAIL_NETWORK_DELIVERY=OFF`. Os 91 arquivos SQL permanecem intactos.
