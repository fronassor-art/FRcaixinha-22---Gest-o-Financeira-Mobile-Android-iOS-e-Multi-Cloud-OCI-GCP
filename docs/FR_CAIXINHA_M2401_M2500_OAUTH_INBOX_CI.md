# AI Studio — M2401–M2500: persistência laboratorial de OAuth e webhook

Base M2400 `e1de6029b265dc46d91a1ef99c65213a5f88015e`, exclusivamente **FR Caixinha AI Studio**, sem alterar FRcaixinha 2.2.

## Implementação (somente CI descartável)

- Migração **032_mp_connect_inbox_ci_only.sql** fora de `backend/migrations`, com guarda obrigatória: somente banco `frcaixinha_ci` e variável `frcaixinha.ci_sandbox=1`. NÃO aplicar em Termux 5433, OCI, produção, staging real.
- Tabela de tentativas OAuth com hash SHA-256 de `state`, hash do redirect e desafio PKCE **sem code_verifier, authorization_code, access_token ou refresh_token**. Consumo atômico de uso único com expiração.
- Vínculo fictício `seller_id ↔ tenant` exclusivo, revogação e impedimento de reativação automática. Sem atestado do Mercado Pago.
- Inbox sintético persistente com exclusividade de notification_id global, request_id e comparação de fingerprint, replays idênticos idempotentes e conflito recusado; não contém JSON bruto, segredo nem token.
- SQL SECURITY DEFINER valida admin da caixinha, contexto e banco descartável a cada operação. Roles de aplicação/autenticação não recebem DML direto; só funções CI restritas.
- Flags forçadas em banco: `provider_get_authenticated=false`, `bank_reconciled=false`, `ledger_written=false`, `paid=false`, `closing_authorized=false`.
- Suíte de integração executada na CI contra PostgreSQL 16 e 18; inclui RLS/privilégios, concorrência, revogação, isolamento, idempotência e replay.

## O que NÃO está pronto

Este pacote não implementa OAuth real, callback público, cofre, troca de tokens, webhook de produção, recebimento de dinheiro, conciliação, baixa, Pix ou fechamento. As funções recebem apenas *fixtures* de CI, não têm nenhum endpoint FastAPI que escreva dados. Não carregar ou migrar estes objetos para o Termux como se fossem integração oficial.

A [Issue #3](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/issues/3) permanece aberta para homologação real por evidência. M2199 exige PR #2 Draft e sem merge.

Próximo trabalho para execução operacional: desenhar migração **separada e revisada** para staging protegido, gerenciador de segredos com rotação e OAuth autorizado por empresa; envelope webhook assinado recebido por HTTPS com fila real idempotente e GET autenticado do provedor, sempre sem escrever no ledger até prova independente.
