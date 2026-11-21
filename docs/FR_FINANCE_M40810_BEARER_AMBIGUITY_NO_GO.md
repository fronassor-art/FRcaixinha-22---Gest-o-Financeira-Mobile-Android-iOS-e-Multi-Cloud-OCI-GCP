# FR Finance M40810 — entrada de Bearer/Cookie sem ambiguidade (NO-GO produção)

## O que foi corrigido no código

`bearer_token` em `backend/app/dependencies.py` agora delega a um parser puro e determinístico antes do SHA-256 e antes de qualquer SQL de autenticação. Ele rejeita cabeçalhos Authorization duplicados, formato não Bearer, Bearer vazio, caracteres fora da codificação URL-safe, espaços adicionais e tokens excessivamente grandes. Um cabeçalho presente porém inválido **não volta silenciosamente para um cookie**. Se o cabeçalho Bearer é válido, tem precedência sobre eventual cookie antigo; sem Authorization, cookie URL-safe continua permitido para compatibilidade com a autenticação legítima.

Este pacote não muda a geração de tokens ou o backend de renovação, não autentica a posse do token por si só e não modifica sessões persistidas. O parser é apenas proteção de entrada e contra ambiguidades HTTP. Contratos e credenciais reais nunca entram nos testes.

## Limites e próximos gates

- O M40730 continua com **NO-GO do emissor SQL**: credencial comprometida aceita emissão sem a assinatura Ed25519, conforme fixture descartável.
- O M40570 continua com **NO-GO do GUC**: SQL arbitrário sob app role pode falsificar `app.current_*`.
- A dependência de sessão PostgreSQL permanece a autoridade real, com revogação, expiração, vínculo e refresh; as regressões completas precisam passar na CI geral.
- O FastAPI original no Termux não foi recarregado; nenhum runtime, processo, PG18 original, migration, rede ou serviço local foi modificado. Não é uma prova de que o código novo está em execução.
- O APK M40510 ainda exige reteste físico do topo após teclado/logout; OCI/Vault/HTTPS e integração financeira real não estão atestados.

`MIGRATIONS=NONE`; `DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`. PR #2 Draft, branch main intocada.

Não sincronizar no Termux antes da CI geral 7/7 do HEAD final; qualquer migração posterior exige avaliação de delta, backup, ensaio de restauração e aprovação específica.
