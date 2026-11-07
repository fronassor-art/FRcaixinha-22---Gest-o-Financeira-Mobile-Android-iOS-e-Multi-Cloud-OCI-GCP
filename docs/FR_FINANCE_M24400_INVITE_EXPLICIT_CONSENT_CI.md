# M24400 — Consentimento explícito no cadastro por convite (CI isolada)

**Escopo: FR Finance AI Studio exclusivamente.** Não altera o FRcaixinha 2.2 independente, não cria máquina OCI, não configura e-mail ou Mercado Pago, não executa SQL no PostgreSQL local 5433, não faz merge e **não autoriza produção**.

## Falha corrigida

A função sintética \`register_new_invited_identity_ci\` podia criar usuário, vínculo e \`contract_acceptances\` para convite sem parâmetro de aceite afirmativo; além disso, aceitava um documento publicado que ainda não tivesse sido associado ao convite.

Agora a função:
1. exige \`consent is True\` (o valor-padrão é \`False\`, portanto negação segura);
2. exige o SHA-256 hexadecimal de 64 caracteres da versão contratual que foi apresentada (\`accepted_document_sha256\`);
3. compara esse hash ao documento publicado identificado pelo \`document_id\`;
4. exige que o \`required_document_id\` persistido no convite seja exatamente essa versão, sem aceitar \`NULL\`;
5. só então realiza criação de identidade, credenciais, aceite e vínculo na mesma transação de laboratório, com auditoria;
6. mantém todos os controles anteriores de token de verificação, convite entregue, expiração, revogação, autorização do convidante, CPF válido e tenant ativo.

O fluxo só opera com \`FRCAIXINHA_CI_ISOLATED=1\`, no banco descartável \`frcaixinha_ci\`, como \`postgres\`, porta 5432. Não há API pública para executá-lo. A rota \`/invitations\` continua negando criação real; não há e-mail entregue ou identidade de produção verificada.

## Evidência acrescentada

- Regressão no PostgreSQL descartável via \`test_aistudio_account_lifecycle_ci.py\`: recusa de consentimento ausente/negado/textual, hash ausente/incorreto, contrato não vinculado, criação única quando todos os controles passam, bloqueio de replay, usuário não Master e vínculo apenas de membro com aceite versionado.
- Regressões sem banco \`test_m24400_explicit_invite_acceptance_ci.py\` conferem padrão de negação, checagem de CPF, vinculação da versão e preservação da rota pública bloqueada.
- Os testes existentes de convite e recuperação continuam no workflow. Nenhum novo privilégio RLS/GRANT foi concedido.

## Relação com as cláusulas

**3.1, 6.1 e 6.1-A:** a prova de laboratório sobre aceite explícito avançou, mas permanecem bloqueadas para operação real devido à ausência de entrega autenticada de convites, titularidade de e-mail comprovada por provedor, proteção antiabuso, aprovações e ativação conciliada. **3.5:** o aceite de licença SaaS para o Administrador da plataforma e a vigência/renovação/cobrança conciliada continuam pendentes.

A classificação histórica das **147 cláusulas** (50 bloqueadas, 34 não verificadas, 58 parciais e 5 divergentes) não foi alterada automaticamente. É necessário atualizar a matriz de evidências e homologar AT-01–50 com contas/tenants sintéticos antes de recomendar liberação.

## Homologação no Termux sem banco ou senhas

\`\`\`bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
python3 backend/scripts/aistudio_contract_gap_audit.py --json
python3 backend/scripts/aistudio_migration_inventory.py repo-check
PYTHONPATH=backend python3 -m pytest -q \\
  backend/tests/test_m24400_explicit_invite_acceptance_ci.py \\
  backend/tests/test_m24300_oauth_recovery_readonly_ci.py \\
  backend/tests/test_m24000_contract_gap_147_ci.py
git rev-parse --short HEAD
git status --short
\`\`\`

**Não executar** \`test_aistudio_account_lifecycle_ci.py\` diretamente no Termux: as integrações de banco desse arquivo exigem PostgreSQL descartável e existem apenas no GitHub CI.
