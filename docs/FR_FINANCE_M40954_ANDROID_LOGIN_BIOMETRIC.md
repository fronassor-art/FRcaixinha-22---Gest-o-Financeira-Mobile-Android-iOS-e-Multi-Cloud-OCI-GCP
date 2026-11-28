# FR Finance M40954 — login Android e preferência biométrica

Ajuste incremental M40510: recalcula a área do login após retornar de
AccessLinkView, acompanha o campo em foco durante a alteração da viewport
e movimenta somente o contêiner interno quando o campo está encoberto.
A tela de seleção mantém o reset de scroll existente. A senha revelada
é ocultada ao sair do primeiro plano ou retornar à seleção de perfil.

A ativação e a desativação da proteção biométrica exigem desafio nativo
recente da mesma conta. O plugin continua consumindo a autorização de
45 segundos; não substitui login nem autenticação no servidor.
Se a biometria do dispositivo estiver indisponível, a preferência
não pode ser alterada por este painel. Logout e login com senha continuam
disponíveis; nenhuma preferência anterior é modificada automaticamente.

Testes determinísticos e estáticos acrescentados às suítes M40510/M40500.
CI não equivale a homologação física: verificar teclado, rotação, logout,
biometria nos dois sentidos e perfil no aparelho após instalação autorizada.
Nenhuma alteração em PostgreSQL, serviços ou configurações financeiras.
PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
