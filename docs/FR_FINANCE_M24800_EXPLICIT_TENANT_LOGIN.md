# M24800 — Seleção explícita de caixinha no login (AI Studio)

Escopo: FR Finance AI Studio. Sem alterar o outro projeto, sem migração,
sem ativação de Pix, e-mail de convite, recuperação de senha ou OCI.

## Problema e resolução

Uma única identidade pode pertencer a várias caixinhas com o mesmo papel.
O login anterior selecionava o primeiro vínculo ativo ao escolher somente
TENANT_ADMIN ou TENANT_MEMBER. Agora o cliente pode informar
`requestedTenantId` no login (ou `requested_tenant_id` na API).

- O campo é opcional para preservar clientes anteriores.
- O servidor converte o identificador para UUID e, após verificar a senha,
  consulta os vínculos ativos permitidos no PostgreSQL.
- Ao informar papel e caixinha, o servidor seleciona somente a combinação
  existente; vínculo ausente provoca 401 genérico e rollback da sessão.
- O perfil MASTER não aceita `requestedTenantId`.
- O frontend confirma que papel e tenant retornados correspondem ao pedido;
  caso contrário, tenta revogar o token devolvido e recusa a sessão.
- Mudança de papel dentro de uma sessão continua bloqueada; requer logout
  e autenticação novamente.
- Fluxo antigo sem `requestedTenantId` não foi alterado; a seleção de
  caixinha na interface visual ainda precisa de UX/homologação separada.

## Cobertura

- `backend/tests/test_master_explicit_login_policy.py`: papel/tenant
  correto, impossibilidade de selecionar tenant estranho, MASTER e fallback.
- `backend/tests/test_aistudio_roles_e2e_ci.py`: identidade de Admin/Membro
  associada a duas caixinhas, segundo tenant selecionado, primeiro tenant
  inacessível por RLS, vínculo inexistente rejeitado.
- `src/tests/mobile_master_multi_role.test.ts`: solicitação de segundo
  tenant e confirmação do vínculo devolvido no cliente.

Testes de E2E PostgreSQL são exclusivos do banco descartável de CI.
Não executar testes E2E na base local da porta 5433.

## Verificação local sem mudança de banco

```sh
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_master_explicit_login_policy.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git status --short
git rev-parse --short HEAD
```

O runtime local deve ser reiniciado em momento apropriado para carregar
alterações de Python; a simples atualização de código não prova que o
processo FastAPI antigo já executa o novo commit.

## Bloqueios preservados

- Convites públicos: 503; não habilitar o motor exclusivo do CI em produção.
- Recuperação de senha: 503 enquanto não houver canal confiável.
- Dinheiro real, cobrança, transferência e fechamento: desativados.
- Aplicação automática de migrações locais: não realizada.
- Não representa API publicada nem APK homologado.
