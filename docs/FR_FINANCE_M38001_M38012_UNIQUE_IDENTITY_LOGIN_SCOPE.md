# FR Finance AI Studio — M38001–M38012 | Identidade única

Checkpoint de partida M38000, commit 0554742, com 1.115 testes Python offline PASS no Termux.

Correção funcional: o seletor de papel do backend não escolhe mais silenciosamente o primeiro vínculo quando um cliente legado omite o perfil. A compatibilidade só é preservada para identidades não Master com exatamente um vínculo. Dois papéis, duas caixinhas ou linhas duplicadas exigem seleção explícita (409 após verificação da senha). Seleções explícitas devem identificar uma combinação única de perfil e caixinha. Master exige papel explícito e não herda contexto financeiro da plataforma.

A tela de primeiro acesso esclarece que uma identidade pode participar de vários tenants e que não se deve criar uma nova identidade para cada vínculo. Os convites públicos, a confirmação de e-mail, a revisão jurídica e a ativação de contas reais permanecem bloqueados.

Testes: seleção independente de ordem SQL; permissões Master, Admin e Membro; papéis falsos; vínculos ausentes, duplicados e de outro tenant; respostas 401/409 sem dados pessoais; guia de primeiro acesso. Nenhuma migração, alteração SQL, envio de convite, ativação ou pagamento.

PRODUCTION=BLOCKED; REAL_PIX=OFF; REAL_ACCOUNTS=OFF; POSTGRESQL_ORIGINAL_UNCHANGED=true.
