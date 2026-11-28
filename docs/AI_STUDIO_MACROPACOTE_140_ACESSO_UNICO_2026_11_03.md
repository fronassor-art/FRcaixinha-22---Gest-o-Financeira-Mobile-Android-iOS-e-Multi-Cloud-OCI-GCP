# AI Studio — Macropacote 140: identidade única e governança de sessão

Data: 03/11/2026. Escopo exclusivo do repositório AI Studio.
Baseline: Macropacote 120 no commit 8c4457048190d5dda8a845151dd3b7294b529574,
CI #197 6/6 PASS; sete testes no APK 197 relatados como executados,
mas aprovação manual PASS/FAIL ainda não explicitada.

**Não autorizar troca de perfil dentro da mesma sessão.** A política vigente
do FastAPI exige logout seguido de novo login por perfil, inclusive para
a mesma pessoa que atua como Master/Administrador/Membro. API e app bloqueiam
switch-context. Esta entrega reforça a fronteira sem abrir endpoints de escrita.

## 20 verificações rastreáveis
| # | Verificação | Implementação/prova | Status |
|---|---|---|---|
| 01 | Identidade única, sem segunda conta Master | authService / testes já existentes | CI |
| 02 | Papéis permitidos estritamente | parseServerContexts | CI |
| 03 | Contexto MASTER sem tenant | parseServerContexts | CI |
| 04 | Contexto de ADMIN com UUID tenant | parseServerContexts | CI |
| 05 | Contexto MEMBER com UUID tenant | parseServerContexts | CI |
| 06 | Campos inesperados de vínculo negados | parseServerContexts / 140 CI | CI |
| 07 | Duplicações por maiúscula/minúscula negadas | parseServerContexts / 140 CI | CI |
| 08 | Resposta do servidor restrita ao contexto autenticado | listContexts / 140 CI | CI |
| 09 | Troca de perfil exige logout | switchContext bloqueado | CI |
| 10 | Bloqueio server-side de switch-context | /auth/switch-context 403 | CI |
| 11 | Role MASTER confirmado na API | require_master + owner-access | CI |
| 12 | Master não consulta tenant financeiro | require_tenant_access | CI |
| 13 | ADMIN não acessa outro tenant | require_tenant_access | CI |
| 14 | MEMBER não acessa outro tenant | require_tenant_access | CI |
| 15 | Sessão atual por papel/tenant | parseServerSessionInventory | CI |
| 16 | Rejeição de campos privados em sessões | lista permitida | CI |
| 17 | Não duplicar sessões na resposta | parseServerSessionInventory | CI |
| 18 | Exibir papel e identificador curto em sessões | SessionSecurityPanel | CI |
| 19 | Revogação e retorno do segundo plano sem ressuscitar sessão | regressões existentes | CI |
| 20 | Compilar APK e homologar 3 perfis no dispositivo | CI+Termux+Android | PENDENTE MANUAL |
    
A enumeração dos itens de CI deve ser auditada no GitHub Actions:
não afirmar completude até o teste concluir.
Não aplicar novas migrations no banco Termux; PG18 CI e PG16 descartáveis,
sem segundo backend, sem novos usuários humanos, sem credenciais reais.
Não movimentar Pix, cobrar SaaS ou declarar fechamento de ciclo.

## Manual após APK
1. Verificar SHA de sete caracteres no cabeçalho.
2. Logar como Master. Conferir tela de sessões e identificação 'Master / Plataforma'.
3. Efetuar logout. Logar como Admin; identificar apenas caixinha correta.
4. Efetuar logout. Logar como Membro; conferir menus e dados próprios.
5. Em outro aparelho/sessão autorizada, revogar uma sessão de homologação
   e observar expiração sem reabrir contexto antigo.
6. Conferir erro/offline sem reapresentar informação de outro usuário.
7. Testar cabeçalho e rolagem, aprovados no APK 195.
Não capturar senhas/tokens/CPF em prints.

**Dependências posteriores:** convites/aceites reais, e-mail verificado, reset,
anti-fraude distribuída, deploy TLS e liberação financeira têm gates separados.
