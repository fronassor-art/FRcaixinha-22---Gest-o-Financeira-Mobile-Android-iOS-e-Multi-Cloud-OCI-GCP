# CHECKLIST — PRIMEIRA INSTALAÇÃO APK AI STUDIO

Snapshot: GitHub PR #2, branch \`atualizacao-ai-studio-9b46a63187\`.
Finalidade: homologação VISUAL/INSTALAÇÃO, sem transações reais.

1. Verifique que o nome do pacote é \`com.frcaixinha.app.aistudio\` (variante debug isolada).
2. Baixe o arquivo .apk, não o ZIP de código; se for ZIP de artefato, extraia \`app-debug.apk\`.
3. No Android, autorize "instalar apps desconhecidos" somente para o aplicativo usado no download, se solicitado; revogue a permissão após instalar.
4. Confira se apareceu **FRcaixinha AI Studio (Teste)** sem substituir outro aplicativo.
5. Abra o app e anote: inicializa? tela branca? mensagem de erro? nome e layout?
6. Teste orientação vertical, botão Voltar, teclado, campos e rolagem.
7. Sem backend em \`127.0.0.1:8000\`, é esperado que login e dados protegidos não funcionem; não tente forçar acesso Master.
8. Não cadastre CPF, e-mail, senha ou dados financeiros reais; não faça Pix nem habilite conexão bancária.
9. Se houver falha, registre horário, ação, tela e mensagem exata; envie print sem credenciais.
10. Verifique se há outro app FRcaixinha instalado e confirme que continua inalterado.

Critério: instalar/abrir e apresentar login de forma íntegra, sem crash. Acessar painel autenticado requer backend de homologação separado e migrações autorizadas futuramente.
