# Pacote AI Studio: etapas 2–5 (02/11/2026)

## Entrega
- Cadastro local de homologacao: a senha do Master autoriza; credencial SQL local
  isola o cluster; cria um tenant e dois vinculos numa transacao com auditoria.
- Admin e Membro: NOVA, EXISTENTE ou MASTER. MASTER reutiliza a identidade,
  e-mail, UUID e senha do unico Master ja autenticado no terminal, sem criar
  segunda conta; o banco grava dois memberships (roles distintos) no tenant.
- Caixinha inaugural: opcao explicita SIM somente quando os dois vinculos
  pertencem ao Master; nao pode marcar uma segunda caixinha inaugural.
- Identidade unica nao altera permissoes: a sessao ativa escolhe contexto,
  RLS impede acesso de Master a saldos, e Membro nao lista membros.
- CI real: PostgreSQL descartavel, login HTTP dos tres papeis, RLS e logout;
  TypeScript smoke simula cliente do APK; Android gera debug APK na mesma SHA.
- **Ativacao real no Termux e testes no aparelho ainda dependem do operador.**

## Regras
Sem alteracoes ao Master existente, sem migrations e sem banco paralelo.
Nao usa convites de email ativos: endpoint public /invitations continua em 503.
Nao considera email confirmado nem habilita pagamento, Pix ou producao.
Nao cadastrar terceiros sem autorizacao deles.

## Depois de sincronizar SHA validada no Termux
Verificar branch Git de desenvolvimento e arvore limpa. Confirmando
a criacao de uma caixinha local de homologacao, executar:

    cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
    AI_STUDIO_ALLOW_ROLE_ONBOARDING=YES \
    python3 -B backend/scripts/onboard_aistudio_roles.py

Senha do Master e senha SQL sao solicitadas diretamente no Termux.
PARA O PROPRIETARIO DO APLICATIVO, escolha MASTER para Admin e para Membro,
e depois SIM para marcar a caixinha INAUGURAL. Nao digite novo CPF, e-mail
ou senha de outra conta. A senha do Master informa-se UMA vez e autoriza
ambos os vinculos, nao existem tres cadastros independentes.
Para terceiros, NOVA coleta dados e senha; EXISTENTE prova senha atual.
Confirmacao final: CADASTRAR_ADMIN_E_MEMBRO_AI_STUDIO.
Nao publicar CPFs, emails pessoais ou senhas nos logs ou no GitHub.

## APK
Manter PostgreSQL e FastAPI na porta local 8000; APK de debug gerado para
http://127.0.0.1:8000. Instalar apenas o artefato da mesma SHA CI aprovada.
Entrar UMA unica vez como Master, abrir o seletor "Meu acesso unico",
alternar Master -> Administrador -> Membro -> Master sem novo login,
conferir UUID/e-mail estaveis, menus especificos, bloqueio de Master
a dados financeiros e bloqueio de Membro a lista administrativa.
Fazer logout e confirmar que o token nao funciona mais.
Build CI nao equivale a homologacao de uso real no celular.
