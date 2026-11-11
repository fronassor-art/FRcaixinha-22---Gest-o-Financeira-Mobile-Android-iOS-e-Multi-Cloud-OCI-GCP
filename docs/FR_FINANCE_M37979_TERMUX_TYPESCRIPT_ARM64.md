# FR Finance AI Studio — M37979 | Falha TypeScript 7 no Termux ARM64

Ponto de partida: commit 5b892c5 (CI geral 6/6 PASS e Termux 615 testes Python PASS). O diagnóstico do usuário mostra Node 24.22.1 e falha de \`npm run lint\` na resolução de \`@typescript/typescript-android-arm64\`. A linha do shell foi interrompida antes de rodar os testes TSX seguintes e o checkpoint final; isso não prova falha do frontend em CI.

## Causa e política
- TypeScript 7.0.2 usa compilador nativo. O pacote nativo para Android/ARM64 não estava disponível para essa versão na instalação atual. O projeto preserva \`typescript@^7.0.2\` e seu lockfile.
- A compilação oficial continua com TypeScript 7 no GitHub Actions Linux, cuja execução original M37978 terminou com sucesso.
- Para o Termux Android/ARM64 usa-se exclusivamente \`@typescript/typescript6@6.0.2\` **fora do repositório**, em \`$HOME/.cache/frfinance-m37979-typescript6\`. Esse \`tsc6\` executa a checagem de tipos local, mas **não substitui a CI do compilador oficial TypeScript 7**.
- Não executar \`npm install typescript@6\` nem editar package.json/package-lock.json; não tentar forçar o binário Linux de TS7 em Android.
- Sem internet ou falha de instalação: o script interrompe sem imprimir PASS; não mascara erros de tipagem.

## Execução depois de sincronizar o commit novo

\`\`\`bash
cd "$HOME/fr-finance" || exit 1
bash backend/scripts/frfinance_m37979_termux_frontend.sh
\`\`\`

Em Android/ARM64, na primeira utilização, o script instala a versão de compatibilidade na cache pessoal. No Linux CI executa \`npm run lint\` com TypeScript 7. Em ambos os casos roda seis testes TSX de autenticação, contexto, API, notificações e Android, usando a instalação já existente de tsx. Verifica a árvore Git limpa antes e depois.

## Limites de homologação
M37979 não cria VM ou aplica SQL, não inicia API/PG, não ativa contas, e não movimenta dinheiro. Uma checagem local TS6 aprovada e uma CI TS7 aprovada não são provas E2E de backend operacional em staging. Mantêm-se os 20 gates técnicos e sete externos sem atestação de produção. REAL_PIX=OFF, REAL_PAYMENTS=OFF, REAL_ACTIVATION=OFF.
