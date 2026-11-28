# FR Finance AI Studio — M38050–M38069: limite de desafios de e-mail no CI

Checkpoint anterior: M38049, commit 31a56a9, 1.194 testes Python aprovados no Termux e CI geral PASS.

Problema corrigido: a função sintética de emitir desafio de verificação de e-mail podia revogar continuamente o token anterior ao criar outro, sem período mínimo nem limite total. Uma reemissão acidental podia inutilizar o link ativo.

Implementação: no máximo três desafios por convite, incluindo os já revogados ou consumidos; intervalo mínimo de sessenta segundos; bloqueio por inconsistência de histórico; consulta de contagem e horário sob lock FOR UPDATE do convite no PostgreSQL descartável. A política é avaliada ANTES de revogar o desafio vigente. Teste de integração confirma que pedidos precoces não invalidam o link, reemissão controlada revoga o antigo, e a quarta tentativa é recusada.

Não há e-mail real enviado, verificação de titularidade por provedor, cadastro público, conta nova real, migração, pagamento ou mutação na OCI. Executor CI continua limitado ao PostgreSQL frcaixinha_ci em porta 5432, jamais frcaixinha_aistudio_dev em 5433.

Testes offline: backend/tests/test_m38050_email_challenge_policy_ci.py e suites existentes. Teste em PostgreSQL descartável: backend/tests/test_aistudio_live_engines_ci.py::test_challenge_rate_limit_preserves_active_token.

A implementação é defesa de laboratório e NÃO libera SMTP, consentimento, identidade, autenticação ou uso real de convites. PIX_REAL=OFF; ATIVACAO_REAL=OFF; PRODUCAO=BLOCKED.
