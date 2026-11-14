# FR Finance AI Studio — M38030–M38049 | Conta existente exige senha atual

Checkpoint de origem: commit 211b4e6, M38029, 1.176 testes Python PASS offline no Termux.

O laboratório existente de aceitação de convite para conta previamente cadastrada validava e-mail verificado, convite entregue, documento publicado e aceite exato, mas não a senha da conta já existente. Um link recebido por e-mail não deveria conferir automaticamente o controle dessa conta.

M38030–M38049 introduz account_password opcional com recusa por padrão e verificação da senha atual Argon2id/bcrypt sob lock transacional FOR UPDATE do hash. Uma credencial errada ou ausente recusa vínculo e aceite, sem alteração de conta. A fixture PostgreSQL descartável testa prova ausente, senha errada e senha válida, mantendo as condições de idempotência, expiração, contrato e escopo. Testes offline exercitam entradas inválidas sem consultar SQL.

O executor continua inacessível por API pública: somente FRCAIXINHA_CI_ISOLATED=1, frcaixinha_ci, postgres, porta 5432, e ambiente não production. Essa operação não é um mecanismo de autenticação pública; não comprova e-mail real, MFA, independência de aprovação, entrega por Brevo ou ativação de contas. Nunca executar essa suite de integração contra frcaixinha_aistudio_dev porta 5433. O pacote não aplica migrations nem altera OCI.

PIX_REAL=OFF. PAGAMENTOS_REAIS=OFF. ATIVACAO_REAL=OFF. PRODUCAO=BLOCKED.
