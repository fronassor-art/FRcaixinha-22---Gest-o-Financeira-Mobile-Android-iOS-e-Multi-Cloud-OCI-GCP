# M23800 — Registro OAuth PENDING antes do CAS

O M23700 chamava a ativação da revisão sem registrar PENDING no SQL. O M23800 utiliza a função existente `public.mp_staging_oauth_stage` (migração de staging 046), antes da ativação e depois da revalidação do consentimento.

`PendingTokenRevision.expected_generation` passa a ser obrigatório para o registro, com inteiro 0..2^63-1 e validação de identidade, tenant, actor, seller, revisão e referência opaca. O backend **não** consulta tabelas privilegiadas nem tenta adivinhar a geração: a fonte autorizada continua pendente. Uma geração obsoleta é bloqueada pelo SQL.

O adaptador permanece desativado por padrão, trabalha com banco simulado nos testes e não cria conexão PostgreSQL, OCI Vault, endpoint público, credenciais reais ou operação Pix. Falhas preservam a revisão ativa e tentam marcar a revisão nova como FAILED e cancelar seu segredo por compensação; não se promete transação distribuída entre Vault e PostgreSQL.

**Pendências:** implementar armazenamento protegido concreto e fonte confiável de geração e consentimento autenticado; após isso homologar com PostgreSQL de staging descartável, OCI e Mercado Pago. Não aplicar migrações de staging no Termux/5433.
