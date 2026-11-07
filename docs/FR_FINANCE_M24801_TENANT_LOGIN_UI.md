# M24801 — seleção explícita de caixinha na tela de login

Frente de trabalho: **FR Finance AI Studio**. Não modifica banco, schema SQL,
papéis, Pix, serviço de e-mail, OCI ou o projeto FR 2.2 independente.

## Mudança funcional

- Administrador e Membro passam a ter o campo opcional **ID da caixinha** na tela de login.
- O ID é um UUID fornecido pelo administrador e não é segredo nem credencial.
- O cliente não armazena a senha, o ID ou tokens permanentemente.
- O login encaminha o UUID ao servidor no campo `requestedTenantId` (M24800).
- O servidor só o aceita se houver vínculo ativo com o papel selecionado.
- Quando há **mais de uma** caixinha ativa para o papel e o ID não foi enviado,
  o servidor recusa com HTTP 409 **depois da verificação da senha**.
- A ausência ou falsificação do vínculo é negada com HTTP 401.
- MASTER nunca apresenta campo de tenant nem aceita tenant selecionado.
- Sem troca de perfil ou de tenant dentro de uma sessão já emitida.

## Limites e homologação

A tela é uma etapa segura de seleção por identificador, **não** é diretório
visual de caixinhas nem liberação de convites públicos. O fluxo ideal de
seleção por nome após autenticação, com desafio transacional, necessita
projeto e testes adicionais para não divulgar vínculos a usuários não
autenticados.

Testes previstos:
- `backend/tests/test_master_explicit_login_policy.py`
- `backend/tests/test_aistudio_roles_e2e_ci.py` — exclusivo CI PostgreSQL descartável
- `src/tests/login_first_access_ui.test.ts`
- `src/tests/mobile_master_multi_role.test.ts`
- Lint frontend, PostgreSQL RLS CI, API sem banco e compilação APK debug.

Só aprovar depois de CI completa e verificação no Termux. Atualização de
arquivos locais não reinicia o FastAPI ativo; não alegar que o runtime já
carregou o novo commit sem evidência.

## Checkpoint Termux — sem aplicação de migrações

```sh
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_master_explicit_login_policy.py \
  backend/tests/test_m24600_invitation_document_binding_ci.py \
  backend/tests/test_aistudio_lifecycle_disabled.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```
