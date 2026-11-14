# FR Finance — M39084 | recuperação local da dependência Capacitor Push (Termux)

## Contexto validado em 13/11/2026
- M39083 sincronizada no Termux até `95459c242e58209debac5fbe577a0f6f2fc716bc`.
- Backend M39083: **47/47 testes PASS**.
- Frontend: TypeScript 7 nativo indisponível no Android ARM64, tratado no projeto pela M37979 com TypeScript 6 isolado.
- Na execução M37979, a compilação TS6 falhou em `src/services/specialCreditPushNative.ts` com `TS2307` para `@capacitor/push-notifications`; os cinco erros de parâmetros `implicit any` associados resultam provavelmente da importação não resolvida.
- O `package.json` e `package-lock.json` já declaram exatamente `@capacitor/push-notifications@8.1.2`, com hash de integridade.
- O resultado local indica falta de resolução do pacote, não prova que o backend, o APK ou o FCM tenham falhado.

## Estratégia M39084
Script: `backend/scripts/frfinance_m39084_termux_push_recover.sh`.
- Executa apenas em Termux nativo Android ARM64, exige árvore Git limpa, npm, Node, Python, tar, tsx e `@capacitor/core`.
- Verifica versão em package/lock antes de modificar qualquer coisa.
- Se o plugin 8.1.2 existir, apenas valida a versão.
- Se faltar, usa `npm pack` com `--ignore-scripts` para baixar o tarball exato para a cache pessoal. **Compara o SHA-512 do arquivo com a integridade fixada no lockfile** e somente então instala os arquivos em `node_modules/@capacitor/push-notifications` (diretório ignorado pelo Git). Não roda instalação global da árvore nem scripts de pós-instalação de dependências.
- Usa M37979 para typecheck complementar TS6 e testes históricos, seguido dos três testes TSX M39083/M39076/M39020.
- Falha fechada em erro de rede, versão, integridade, tipagem, teste ou alterações versionadas. Não imprime PASS prematuro.
- Sem alteracão de `package.json`, `package-lock.json`, TypeScript 7, backend financeiro, banco original PostgreSQL, credenciais, provedores, Pix, ativação, APK ou OCI.

## Execução
Após verificar CI e sincronizar commit M39084 na branch AI Studio, executar **no Termux nativo**:

```bash
cd "$HOME/fr-finance" || exit 1
bash backend/scripts/frfinance_m39084_termux_push_recover.sh
```

A CI M39084 valida sintaxe, invariantes de segurança, versões declaradas e, no Linux, TypeScript 7 oficial. A instalação do pacote Android e o typecheck local exigem o retorno de logs reais do aparelho. Mesmo com PASS local, não declarar push real nem produção homologados.
