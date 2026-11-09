# FR Finance AI Studio — M36400–M36800 | Conferência SaaS de três fontes (CI)

**Checkpoint anterior:** M36300 homologado (`685f6f8fa56aaba97416b2ee81ba5ce7088ac981`).

## O que foi criado

O módulo `backend/app/saas_three_source_review_ci.py` realiza uma **avaliação
puramente local de evidências sintéticas**, exclusivamente da plataforma SaaS
FR Finance, sem tocar saldos ou valores de caixinhas.

O contrato confronta:

1. **Registro SaaS PostgreSQL simulado**: intenção, tenant, administrador,
   conta recebedora da plataforma, versão do preço e centavos esperados.
2. **Readback simulado vinculado ao M35800**: resultado de conferência
   `RLS_PRICE_PROVIDER_MATCH_REVIEW_ONLY`, identificador, coletor, referência,
   valor, ausência de reembolso e hash SHA-256.
3. **Extrato de liquidação sintético independente**: valor bruto, tarifa,
   valor líquido, banco/referência, datas e SHA-256 distinto.
4. **Trilha M36300 simulada**: um candidato de GET correspondente,
   nenhuma duplicação, reversão ou indisponibilidade ativa.

Também exige **quatro identificadores diferentes** para o administrador,
observador do GET, observador do extrato e revisor independente.
A distinção de IDs **não autentica pessoas reais** e não substitui controle
de acesso/MFA ou segregação operacional de produção.

## Bloqueios e validade

- GET consultado há no máximo 15 minutos; extrato observado há no
  máximo 24 horas. Futuro e data sem fuso horário bloqueiam.
- Cobrança e plano têm valores de centavos exatos; deve valer
  bruto = tarifa + líquido; refund sempre zero.
- Tenant, ID da intenção, ID do pagamento, coletor SaaS, referência
  e moeda BRL devem coincidir.
- Hash do GET deve corresponder ao retornado pelo M35800, sem concessões
  de autorização ou escrita. Hash do extrato deve ser válido e diferente.
- Revisão de estorno ou indisponibilidade prevalece sobre candidato
  de aprovação, ainda que a simulação anterior fosse positiva.
- Resultado positivo é somente
  `CI_THREE_SOURCE_CONGRUENCE_REVIEW_ONLY`, **nunca**
  `licença ativa`, `pagamento recebido` ou `Pix liberado`.

## Limite de alcance

Todos os dados utilizados são fixtures; os identificadores e hashes são
valores declarados, **não provas criptográficas** de Banco Central,
Mercado Pago, banco ou cofre. O módulo não possui cliente HTTP,
acesso ao PostgreSQL, endpoint, worker, I/O nem escrita de eventos reais.
Não cria um token operacional de autorização.

A futura implementação em OCI precisará buscar as três evidências
de canais independentes e autenticados, validar assinatura/proveniência,
usar papel PostgreSQL restrito, capturar carimbo de tempo íntegro,
armazenar os documentos brutos cifrados, validar dupla aprovação,
conferir status imediatamente antes do commit e preservar trilha
append-only com backup e retenção.

**Bancos locais/OCI:** nenhum SQL aplicado. Catálogo permanece com
**106 SQL**. Migração 065 continua CI-only. Pagamentos e Pix reais
continuam desligados, sem usuários reais ativados.

## Bloqueios de implantação fora da CI

VM OCI de staging funcional, DNS/HTTPS, Oracle Vault/IAM, SMTP/DKIM,
confirmação comercial dos acessos do Mercado Pago e comprovantes
autênticos são necessários para validar controles de produção. A
aprovação desta simulação não altera o status dos 20 gates técnicos e
7 externos, que continuam sem comprovação operacional.
