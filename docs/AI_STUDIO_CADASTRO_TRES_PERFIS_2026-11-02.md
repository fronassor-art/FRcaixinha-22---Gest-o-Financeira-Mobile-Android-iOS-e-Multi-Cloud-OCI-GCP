# Pacote AI Studio: etapas 2–5 (02/11/2026)

## Entrega
- Cadastro local de homologacao: a senha do Master autoriza; credencial SQL local
  isola o cluster; cria um tenant e dois vinculos numa transacao com auditoria.
- Admin e Membro: NOVA identidade ou EXISTENTE com prova da senha atual;
  identificador unico nao e duplicado. CPF e e-mail repetidos sao recusados.
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
Para cada Admin/Membro, NOVA coleta dados e senha; EXISTENTE prova senha atual.
Confirmacao final: CADASTRAR_ADMIN_E_MEMBRO_AI_STUDIO.
Nao publicar CPFs, emails pessoais ou senhas nos logs ou no GitHub.

## APK
Manter PostgreSQL e FastAPI na porta local 8000; APK de debug gerado para
http://127.0.0.1:8000. Instalar apenas o artefato da mesma SHA CI aprovada.
Logar e sair dos tres perfis, conferir menus e bloqueios por papel e tenant.
Build CI nao equivale a homologacao de uso real no celular.
