# AI Studio — P0-01a: contexto nomeado limitado por sessão (02/11/2026)

**Projeto exclusivamente AI Studio.** Repositório: `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`; branch `atualizacao-ai-studio-9b46a63187`; PR #2 em rascunho. Os nomes legados no código **não** identificam o outro projeto independente. Não transportar decisões, dados ou infraestrutura entre projetos.

## Escopo efetivamente implementado

- Migração **020** acrescentada à sequência versionada, preservando intacta a 019 e eliminando sua antiga assinatura `auth_active_membership_contexts(uuid)`.
- A nova assinatura `auth_active_membership_contexts(text)` recebe o **token bruto de uma sessão** e faz seu SHA-256 no PostgreSQL usando `pgcrypto` da migration 001. O token bruto não é persistido nem retornado no JSON.
- A função `SECURITY DEFINER` confere sessão não revogada, não expirada, usuário `ACTIVE`, contexto corrente legitimado por vínculo ou perfil MASTER, e somente então consulta nomes dos vínculos ativos.
- `/api/v1/auth/contexts` usa o token recebido na requisição; não consulta a função de nomes com UUID arbitrário.
- Concessão de `EXECUTE` exclusiva ao papel `frcaixinha_auth_role`; o papel financeiro continua sem autorização para essa função ou para `public.sessions`.
- Testes novos na suíte sintética do PostgreSQL 16 verificam: UUID arbitrário não enumera nomes, hash armazenado não serve como token bruto, token inexistente não retorna vínculos, sessão válida retorna apenas sua identidade, e token revogado não retorna dados. No PostgreSQL 18, preflight verifica assinatura nova, ausência da antiga e privilégios.
- Pipeline e script de migração **futura** passam a contemplar 001–020. **Apenas ambientes CI descartáveis** podem aplicar nesta etapa.

## Situação e limitações importantes

Este é um **subpacote parcial de P0 A02/A03/A06**, não uma homologação total. A função histórica `auth_active_memberships(uuid)` da migração 006 ainda é utilizada para descobrir vínculos durante o login; sua superfície de enumeração por credencial Auth requer redesenho do fluxo pré-sessão e teste independente. O papel de autenticação ainda possui acesso estritamente concedido a hashes de senha e hashes de sessão para suportar o login atual. Não declarar prevenção integral de abuso de credencial de serviço.

Outros itens que **não** são resolvidos por este subpacote: inspeção completa de todos os endpoints e privilégios, política de expiração absoluta e anti-abuso distribuído, prova de acesso em dispositivo físico, recuperação de senha, cadastro real e qualquer movimentação financeira.

A CI prova apenas os testes específicos executados, não produção. O relatório de CI deve ser anexado depois da execução no commit final.

## Gates imutáveis

- **Sem aplicação da migração 020 ou das anteriores no Termux**. O PostgreSQL exclusivo do AI Studio foi reportado como versão 18.6, porta 5433, banco `frcaixinha_aistudio_dev` e zero tabelas; esta rodada **não o acessou**.
- Sem credenciais MP/SMTP reais, clientes reais, convites públicos, empréstimos, Pix, pagamentos SaaS, instalação de APK ou merge na `main`.
- Sincronização GitHub→Termux apenas com branch limpa, `git fetch`, `git merge --ff-only` e `bash backend/scripts/aistudio_db_local.sh check`; comparar o HEAD remoto exato antes de atualizar.
- Reclassificar cláusulas 147 e AT-01…AT-50 somente após prova específica; manter histórico da matriz sem declaração automática de `CONCLUÍDO`.

## Próximas tarefas

1. Redesenhar o acesso pré-login `auth_active_memberships(uuid)` sem permitir enumeração arbitrária por conta técnica comprometida.
2. Auditar transações de login/context switch/revogação sob concorrência e sessão expirada.
3. Cobrir por testes CRUD todas as autorizações MASTER/TENANT_ADMIN/TENANT_MEMBER em múltiplas caixinhas.
4. Consolidar `README` e documentos anteriores em uma matriz de fatos datados, sem apagar históricos.
