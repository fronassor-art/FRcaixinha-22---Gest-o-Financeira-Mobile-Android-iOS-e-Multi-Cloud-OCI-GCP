# M40968 — nonce explícito vinculado à prévia Capital-Dias

## Escopo

O envelope M40967 agora exige um nonce explícito e não vazio, limitado a 128 caracteres sem espaços externos. O nonce aparece na resposta e é incluído na serialização coberta pelo SHA-256. Repetir os mesmos dados, versão de política e nonce preserva o digest; nonce diferente produz digest diferente.

Rastreabilidade: Contrato Técnico V2.2, TEC-03 (prévia vinculada ao contexto, à configuração/versão da política e a nonce); TEC-04 (integridade e versionamento do cálculo). O cálculo continua source-only e não integra o processo de abertura ou fechamento de ciclo.

## Testes

`src/tests/m40968_capital_days_nonce_v22.test.ts` cobre repetição determinística, distinção entre nonces, e rejeição de nonce vazio ou com espaços externos. O workflow M40968 roda lint e regressões M40965–M40968.

## Limites

O nonce é fornecido pelo chamador; o pacote não o gera, não registra consumo, não impõe uso único e não detecta replay. Não há persistência, API, assinatura, autenticação, autorização, snapshot definitivo, liquidação, SQL ou migração. O hash não prova que a política ou os eventos vieram de fonte confiável. Anti-replay e revalidação no commit exigem implementação transacional e validação server-side, ainda inexistentes neste preview.

Flags reais permanecem OFF; produção permanece bloqueada. Sem acesso ao PostgreSQL original ou alterações de runtime.
