# FR Finance M37441 — auditoria 3+2, sem afrouxar o saneamento

M37440 no Termux: entre 18 contagens, SOMENTE audit_events divergiu:
3 esperados, 5 observados. A auditoria anterior M37436 encontrou
três eventos no tenant afetado; isso NÃO prova se os dois eventos novos
estão fora do tenant, pois as consultas ocorreram em horários diferentes.

M37441 altera o valor global esperado para cinco, mas ADICIONA a
prova conservadora da distribuição **3 ligados à caixinha / 2 fora**
e **zero referências externas** ao valor ou ciclo antigo. Se forem
cinco eventos no mesmo tenant, a migração permanece bloqueada e
exibe apenas contagens. Não mascara diferenças, não apaga logs
gerais e não consulta dados pessoais para apresentação.

O SQL transacional verifica essas condições novamente após bloquear
tabelas, preserva os cinco eventos e acrescenta um sexto evento
documentando a exclusão excepcional da revisão sintética antiga.
O PostgreSQL 18 descartável no GitHub recebeu dois eventos de
auditoria globais fictícios para testar a condição 3+2 e o rollback.

**Este commit não executa a limpeza no banco local.** Mesmo banco
frcaixinha_aistudio_dev, mesma branch, mesmo diretório Termux.
A aplicação depende do CI 6/6 aprovado, preflight local PASS,
backup cifrado verificável e dois consentimentos explícitos.
Se os dois eventos adicionais também pertencerem à caixinha,
proibido executar apply até uma revisão distinta das referências.
