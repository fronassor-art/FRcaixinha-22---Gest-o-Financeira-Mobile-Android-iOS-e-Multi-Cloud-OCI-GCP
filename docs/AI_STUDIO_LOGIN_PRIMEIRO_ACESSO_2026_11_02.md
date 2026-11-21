# Interface de primeiro acesso — AI Studio (02/11/2026)

Origem: capturas do APK mostraram login sem orientacao de primeiro acesso
e parágrafos técnicos longos. O Android também parece carregar bundle
antigo: calendário superior e selo 2.2, embora o commit anterior
tivesse ocultado o calendário mobile e alterado o selo para AI.

## Ajustes entregues na PR #2
- Tela de entrada: aba Entrar (e-mail/senha únicos para 3 perfis) e
  aba Primeiro acesso com caminhos Novo membro e Novo administrador.
- Ambos os caminhos de primeiro acesso EXPLICAM a necessidade de
  convite ou autorização, SEM criar usuário, convidar ou gerar token
  enquanto a API de convites responder 503.
- Recovery by e-mail indisponível: texto honesto, sem enviar solicitações.
- Menos texto, nenhum contrato/stack ou advertência técnica extensa no login.
- Dashboard único baseado somente em dados permitidos pelo backend,
  sem blocos demonstrativos legados nem ações financeiras não conectadas.
- Badge de build SHA abreviado no login e cabeçalho, embutido pelo
  GitHub Actions no APK para identificar versão no celular.
- Nenhuma alteração em users, credentials, PostgreSQL ou migrations.
- Publicação em PR Draft; ainda exige CI PASS e teste físico no APK.

## Segurança
O papel é selecionado exclusivamente entre vínculos autorizados pelo
servidor APÓS login. Não existe auto-cadastro administrativo, inscrição
pública de membro, envio de e-mail real ou ativação de contas sem convite.
A interface só descreve etapas futuras; não simula que foram concluídas.
