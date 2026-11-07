# FR Finance AI Studio — Macropacote M25900: convite transacional em staging

## Checkpoint anterior: atestação local M25700

O operador executou e informou no Termux `1955004`:
- Testes M25800 locais: **78 PASS**, árvore Git sem modificações;
- Banco exclusivo `frcaixinha_aistudio_dev`, PostgreSQL 18.6, porta `5433`;
- Tabelas públicas: **46**; M028–030, M031, M034–041, M042, M043 e M044
  **objetos, políticas RLS, privilégios e triggers verificados**;
- M043: `OBJECTS_AND_MINIMUM_VERIFIED`;
- M044: `OBJECTS_AND_ROLE_BOUNDARY_VERIFIED`;
- `M19200_READ_ONLY=PASS`, sem migração aplicada durante a auditoria.

A presença estrutural e as permissões NÃO fornecem histórico criptográfico
independente da aplicação arquivo a arquivo de 001–027; isso permanece como
pendência de rastreabilidade. Não reaplicar migrações existentes.

## M25900: fila de convites transacional em banco descartável

Novos arquivos:
- `backend/staging_migrations/050_invitation_outbox_staging_only.sql`
- `backend/ci_migrations/046_invitation_outbox_fixture_ci_only.sql`
- `backend/ci_migrations/047_invitation_outbox_worker_probe_ci_only.sql`
- `backend/tests/test_m25900_staging_outbox_contract_ci.py`

O staging descartável contém duas tabelas: outbox de intenção de envio e
auditoria de enfileiramento. A função `invite_enqueue_held_staging_ci`
recebe convite, evento, digest de destinatário e referência opaca de
envelope sintético; **não recebe e não grava o token real**, CPF, senha
ou credenciais SMTP. O efeito de enfileiramento e auditoria ocorre na
mesma transação. A operação valida o convite ativo, papel do convidante,
caixinha ativa, documento de adesão publicado e correspondência do
digest do destinatário. O bloqueio transacional com advisory lock,
a chave única por convite/evento e a comparação de repetição impedem
duplicidade não detectada e replays com payload diferente.

O estado da fila é imutavelmente `HELD_CI_NOT_SENT`; os campos
`provider_delivery_confirmed` e `recipient_verified` são sempre
`false`. A role `frcaixinha_invite_queue_ci` não recebe SELECT ou
INSERT na tabela; somente EXECUTE da função restrita, que verifica
`session_user`, nome de banco e flag explícita CI. Staging não é
um serviço público. Não há worker SMTP efetivo, nem marcação de
DELIVERED, nem aceite ou concessão de conta.

A migração é registrada no catálogo com o SHA Git e marcada
`STAGING_ONLY_NEEDS_PORT`; as fixtures são `CI_ONLY_TEST_OR_FIXTURE`.
**Jamais aplicar qualquer uma das três no Termux/OCI/prod.**
Catálogo passa de **73 a 76 SQL** e a regressão de inventário deve
confirmar os 76 hashes.

## Ensaios obrigatórios

A CI da API verifica que os arquivos são exclusivos do staging e sem
chamadas públicas. O script `aistudio_staging_chain_ci.sh` provisiona
`frcaixinha_staging` a partir de banco descartável na porta 5432,
prova recusa da migração no banco errado e executa o fluxo SQL restrito.
Exige `NEW` uma vez, `REPLAY` para evento idêntico, conflito para
evento alterado, destinatário divergente e referência não sintética.
Confere uma linha no outbox e uma na auditoria, ambos ainda sem envio,
e rejeita SELECT direto pelo trabalhador. GitHub Actions continua
compilando o APK depois das outras suites.

## Próximas implementações necessárias

- Outbox **operacional**, com envelope cifrado sob KMS, chave por ambiente,
  nonce seguro, controle de acesso e retenção; não usar `ci://` em produção.
- Worker autônomo que consome lote com lease, idempotência, timeout, retry,
  limite de tentativas e auditoria, sem relançar tokens após falha ambígua.
- Evidência do provedor distinta do ACK SMTP; callback de entrega assinado,
  falhas/bounces e prova independente de titularidade por token de uso único.
- Fluxo separado de recuperação de senha, com alteração de credencial
  atômica e revogação de sessões existentes.
- Para administrador, MFA Master e aprovação independente; para membros,
  autorização do administrador ativo do tenant, consentimento informado
  do destinatário e documento canônico efetivamente exibido.
- Implantação OCI com HTTPS, segredos protegidos e revisão de RLS externa.

Este pacote aumenta a implementação verificável, mas NÃO habilita o envio
de convites, recuperação de senha pública, PIX real ou fechamento financeiro.
