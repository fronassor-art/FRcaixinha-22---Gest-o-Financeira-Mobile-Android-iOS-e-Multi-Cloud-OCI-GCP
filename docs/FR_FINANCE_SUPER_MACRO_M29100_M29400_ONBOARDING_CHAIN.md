# FR Finance AI Studio — Supermacropacote M29100–M29400

**Escopo:** branch AI Studio exclusiva, PR #2 draft. Não altera
FRcaixinha 2.2 independente, script M28619 da Oracle, banco local
PostgreSQL 18 na porta 5433, contas reais, entregas SMTP ou Pix real.

## M29100 — correlação de ator, papel, tenant e revisão

Adicionado `backend/app/onboarding_chain_policy.py` com avaliação
estritamente **sintética, determinística e sem I/O** de duas jornadas:

- Master (sessão Master sem tenant) → Administrador de caixinha;
- Administrador (sessão no tenant A) → Membro do mesmo tenant A.

Rejeita cruzamento de tenant, autopromoção, autoaprovação, substituição de
destinatário, papéis incompatíveis, ausência de alegação de MFA no Master
e revisão concorrente inconsistente. Mesmo um cenário sintético consistente
**nunca representa aprovação independente realmente persistida**.

## M29200 — convite e desafio de e-mail

A correlação exige o mesmo convite, destinatário e tenant nas evidências
hipotéticas, validade temporal, não revogação, contagem unitária de consumo
e estado de entrega. Evidências alegadas pelo chamador não são validação de
posse da caixa de e-mail; somente fluxo de provedor e SQL transacional
segregado poderão comprovar isso em staging.

## M29300 — contrato e sessão individual

Compara SHA-256 em formato canônico, ID do documento publicado,
documento referido no convite, aceite afirmativo do próprio destinatário,
role e tenant da sessão resultante. Não registra aceite, não cria sessão,
não confunde `SMTP_ACCEPTED` com entrega e não substitui RLS.

## M29400 — recuperação, replay e testes adversariais

A avaliação exige consumo unitário do token de recuperação e revogação
da família anterior de sessões quando a rotação é hipoteticamente
declarada. O arquivo
`backend/tests/test_m29100_m29400_onboarding_chain_ci.py` contém
cenários positivos **apenas de consistência matemática** e negativos de
replay, escopo e concorrência, além de assegurar que as rotas HTTP reais
de convite e recuperação continuam recusando operações.

O workflow `.github/workflows/validacao-atualizacao.yml` inclui a nova
suíte no job de backend sem banco. A suíte **não** comprova implantação
PostgreSQL, domínio e-mail, consentimento jurídico, MFA, assinatura APK
nem autorização de produção.

## Verificação local segura no Termux normal

```bash
cd "$HOME/frcaixinha-aistudio-mobile"
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m29100_m29400_onboarding_chain_ci.py
PYTHONPATH=backend python3 backend/scripts/aistudio_m29100_m29400_checkpoint.py audit
git rev-parse --short HEAD
git status --short
```

Sem migrations, sem conexão OCI e sem tocar no PostgreSQL 5433.

## Bloqueios que permanecem

1. Atestar Master MFA, aprovador distinto e autorização transacional real.
2. SQL em staging para desafio e convite de uso único sob concorrência;
   e-mail real verificado por provedor homologado.
3. Publicação do texto integral canônico, aceite do destinatário e RLS.
4. Cadastro e login com sessão individual, logout, reset e revogação
   demonstrados end-to-end em staging e no APK instalado.
5. OCI pública, TLS, backup, paridade de migrações, Android assinado
   e demais 20 requisitos / 7 gates externos do M29000.

**Conclusão:** política de correlação reforçada e testável; nenhuma
conta ou movimentação real liberada.
