# FR Finance M34400–M34800 — admissão transacional vinculada a provas (CI)

Checkpoint de origem: M34300 `c0fd205090ad8fbe671feb639d90dadcd49cbcfb`.
Projeto AI Studio, PR #2. Produção, Pix e criação de membros reais OFF.

## O que foi implementado

A migração de staging descartável 064 cria uma trilha de **intenção de admissão**
com papel CI exclusivo. Ela une, sob **lock FOR UPDATE do tenant**, os
dados imutáveis de uma reserva previamente reivindicada e:

- responsável TENANT_ADMIN ativo e a mesma caixinha;
- licença temporalmente válida, plano conhecido, pagamento **sintético**
  aprovado/conciliado em banco (não consultado junto ao Mercado Pago);
- convite entregue, não expirado e não revogado para TENANT_MEMBER;
- pessoa existente, ativa, não Master e com e-mail verificado;
- prova consumida de titularidade do endereço vinculado ao convite;
- documento TENANT_MEMBERSHIP publicado e aceite pela mesma pessoa,
  mesma caixinha e evidência `CI_VERIFIED_IDENTITY`;
- ocupação e reservas coerentes com os limites comerciais do plano.

A trilha resultante possui unicidade por request, claim e convite,
impede dupla admissão concorrente, rejeita cross-tenant e não permite
UPDATE, DELETE nem TRUNCATE. A consulta retorna estados sem expor CPF,
e-mail, credenciais ou tokens.

**A tabela e o procedimento não criam vínculos, cotas, contas, tokens,
e-mail, receita, Pix, convites, nem pagamentos.** Não são um endpoint
público e nunca são aplicados à porta 5433 ou OCI. O novo SQL é
`backend/staging_migrations/064_saas_member_admission_intent_staging_only.sql`.

## Limites e riscos de produção ainda abertos

A evidência de pagamento é exclusivamente uma fixture PostgreSQL da CI;
**não corresponde a um readback autenticado pelo Mercado Pago**.
O próprio claim e o aceite são sintéticos. O fluxo de emissão, aceite e
ativação real continua bloqueado pela migração candidata 046 (não aplicada)
e pelas verificações externas de e-mail, plano e provedor.

Para transformar a intenção em admissão verdadeira, ainda será necessário:
um worker de produção segregado e revisado; interface assinada de
verificação externa; política de consentimento real com prova; proteção
contra mudanças de licença no meio da transação; função atômica de
criação de membership/quota com GRANT mínimo; logs íntegros e ensaios
de recuperação no ambiente OCI com backup. Não implementar atalhos via
credenciais PostgreSQL de proprietário.

**Cuidado com reservas em lote:** a suíte M32800 utiliza também uma
reserva sintética de 20 vagas. O teste M34800 não reaproveita essa reserva
como se fosse uma vaga: ele cria uma caixinha isolada com licença fictícia,
reserva exatamente **uma vaga** e vincula a única intenção ao claim e à
pessoa, com restrição UNIQUE por par (tenant, pessoa). Toda simulação ocorre
exclusivamente no banco descartável da CI.
