# FR Finance M40560 — Exercício adversarial de SaaS/RLS com papéis sintéticos

**Data:** 18/11/2026. **Baseline:** M40550 `8e84d52386fd8cb12fed210a6afad4ab6dee6401`. **Status de produção:** NO-GO.

## Evidências operacionais previamente informadas pelo operador

O M40550 foi sincronizado e executado no **Termux nativo** `8e84d52` contra o PostgreSQL 18 original `127.0.0.1:5433/frcaixinha_aistudio_dev` com senha oculta: identidade PASS; SQL112 estrutura e ausência de UPDATE histórico PASS; SQL113 RLS Master, privilégios mínimos, funções e gatilho PASS; `ROLLBACK_READ_ONLY`, sem linhas de aplicativo consultadas e sem writes/restarts. **Não confundir catálogo aprovado com execução RLS data-plane real.**

## Novo teste independente na CI

`backend/tests/m40560_saas_role_dataplane_disposable.py` inicializa somente o **PostgreSQL 18 descartável** do GitHub em `127.0.0.1:55433/fr_m39067_disposable_ci`, sob guardas de identidade redundantes. Reutiliza a base sintética M39067 e aplica SQL112/113 **apenas** nesse banco efêmero. Os blocos DO que exigem o PGDATA físico do Termux são suprimidos somente em memória no CI; os arquivos de migração reais não mudam.

Exercícios: valores anuais legados preservados, administrador Master fictício validado em allowlist, tentativa de inserção por membro e falso Master negada pela RLS (SQLSTATE 42501), isolamento da leitura Master por papel/identidade, UPDATE/DELETE SaaS e preço histórico negados, função guard não executável pelo papel app, oferta publicada para administrador novo legítimo, mismatch de tenant e membro sem acesso, usuário de autenticação sem SELECT e sem EXECUTE. O teste deixa explícito que a oferta publicada pode ser vista por qualquer administrador novo elegível, não somente pelo criador.

**Limitações explícitas:** autorização de identidade é simulada por contextos SQL fictícios e allowlist; nenhuma sessão real FastAPI, MFA Master, assinatura de token, staging OCI, provedor, webhook, pagamento, backup ou publicação Android é atestada. Credenciais DB da CI são fictícias. O teste não substitui a revisão de possíveis falsificações de GUC por clientes ou de `SECURITY DEFINER`. `AT-01...AT-50` e gates de produção continuam sem aceite.

**M40560_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED; FR_CAIXINHA_2_2=NOT_ACCESSED; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.**
