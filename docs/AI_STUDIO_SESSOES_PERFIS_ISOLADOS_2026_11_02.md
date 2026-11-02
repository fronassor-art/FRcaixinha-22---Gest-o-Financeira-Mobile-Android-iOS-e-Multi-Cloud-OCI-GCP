# AI Studio — Áreas isoladas Master, Administrador e Membro

Decisão operacional em 02/11/2026: **cada sessão terá um único papel**.

- Tela sem login: escolher área MASTER, TENANT_ADMIN ou TENANT_MEMBER;
  depois informar a senha. A seleção é apenas pedido, não autorização.
- API verifica a credencial e vínculo ativo antes de promover sessão no banco.
- MASTER: só funções da plataforma, nunca painéis de membros/administradores.
- TENANT_ADMIN: somente a caixinha e operações permitidas ao administrador.
- TENANT_MEMBER: somente suas contribuições, empréstimos e resultados individuais.
- Perfil ativo: apenas rótulo estático, sem seletor ou opção Trocar Perfil.
- Mudança de área: **Sair da conta** para revogar sessão e iniciar novo
  login com escolha do outro perfil e senha; a identidade/conta existente
  pode deter múltiplos vínculos, sem cadastros duplicados.
- Endpoint POST /api/v1/auth/switch-context devolve 403 em sessões
  válidas; GET /api/v1/auth/contexts lista somente o vínculo atual.
- Serviço cliente recusa novo login sobre sessão ativa e rejeita role/tenant
  inesperados retornados no GET /me.
- Testes sintéticos de CI verificam bloqueios cruzados e logout/login.

Compatibilidade: clientes anteriores da homologação sem requestedRole seguem
com escolha original no backend. **Um APK antigo ainda pode exibir seletor
antigo**, mas o novo backend deve negar /switch-context. Para garantir
comportamento observado, atualizar APK e reiniciar FastAPI após sincronizar
o código do repositório.

Sem dados reais alterados, sem migrations novas e sem merge com main.
