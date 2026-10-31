# Auditoria técnica — FRcaixinha 2.2 exportado do Google AI Studio

Data de referência: 31/10/2026 UTC. Escopo: árvore Termux que produziu o APK, comparação com `main` e CI da branch `audit/termux-apk-20261031`. Auditoria estática e de build; não houve teste funcional no celular nesta etapa.

## Resumo executivo

O APK local contém o bundle web da árvore Termux: o SHA-256 do JavaScript dentro do APK é igual ao de `dist/assets/index-46h2HVbK.js`. A árvore foi sincronizada em branch separada, preservando a `main`. O projeto compila como frontend e tem um invólucro Android/Capacitor, mas **não satisfaz o núcleo financeiro do contrato para operação real**. Identidade e papéis são selecionáveis sem autenticação; dados e lançamentos são mutáveis em `localStorage`; Pix e nuvem são simulações; os cenários AT podem declarar PASS sem executar o comportamento descrito. A interface contém afirmações de integração e segurança que o código não comprova.

## Baseline, origem e inventário

| Estado | Referência | Evidência |
|---|---|---|
| Remoto | `origin`: `https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git`; `main` em `ad61a1e33485f91d4425455c31561c860465b2ec` | `git remote -v`, `git ls-remote origin refs/heads/main`, `gh api .../git/ref/heads/main` |
| Termux inicial | `~/frcaixinha-aistudio-mobile`, branch `main`, HEAD igual ao remoto; árvore suja | `git status --short --branch --ignored` antes de qualquer escrita |
| Termux sincronizado | `audit/termux-apk-20261031`, primeiro commit `8b2faa20c6189dcfdc38c63a2a0759d6b6847064` | `git commit`, `git push -u origin audit/termux-apk-20261031` |
| APK local | `android/app/build/outputs/apk/debug/app-debug.apk`; cópia em Downloads idêntica | 5.434.026 bytes; SHA-256 `3d47bd2bb1000f7c622b42274b57b58db27fc239eecb1a9063c5a6494c08f713` |

O APK declara `com.fronassor.frcaixinha.aistudio`, versão Android `1.0`, `minSdk 24`, `targetSdk 36`, permissão INTERNET e flag debug. O JS do APK e o `dist/` local têm SHA-256 `466e90dba0e8481e6d054c9ded7271f7b9273302e8c70552d784cac8083c2af0`. Isso comprova a igualdade do bundle principal, não a reprodutibilidade binária integral do APK.

Na árvore inicial, `package.json` e `dist/index.html` estavam modificados; dois assets antigos em `dist/assets/` estavam removidos e dois novos não rastreados. `package-lock.json`, `capacitor.config.ts`, `android/` e `node_modules/` não eram rastreados. O commit remoto contém `bun.lock`, sem `package-lock.json`, Capacitor ou Android. Fontes `src/`, `public/`, `README.md`, `index.html` e configurações Vite/TS eram iguais aos objetos do commit remoto.

Arquitetura: React 19 + Vite 8 + TypeScript 7; entrada `index.html` → `src/main.tsx` → `src/App.tsx`; telas em `src/components/`; tipos em `src/types/index.ts`; estado e regras em `src/services/`; Service Worker e manifesto em `public/`; Capacitor 8 e Gradle 8.14.3/AGP 8.13.0 no Android local. Não há diretório de backend, migrações, API ou provedor Pix. Scripts: `dev`, `lint` (`tsc --noEmit`), `build`, `preview`, `clean`; não há script `test`. Antes da sincronização não havia workflow nem histórico de Actions.

Ferramentas Termux: Node 24.22.1, npm 12.2.1, OpenJDK 21.0.13, aapt2 2.20. Vite `^8.3.0`, React `^19.0.1`, TypeScript `^7.0.2`, Capacitor `^8.6.0` e esbuild `^0.28.2` constam do manifest local; o lock local fixa Capacitor 8.6.0, TypeScript 7.0.2 e esbuild 0.28.2. Em `main`, esbuild é `^0.25.0`. O manifesto local e seu npm lock foram sincronizados sem ajuste adicional.

## Contrato técnico e método

Origem confirmada: `public/assets/aistudio/FRcaixinha_2.2___Contrato_T_cnico_Mestre_ORIGINAL_LIMPO_7b28d5d5.pdf` é rastreado no commit inicial e sem diff local; sua cópia está nos assets Android. SHA-256 do PDF: `7b28d5d5cf773fb5c35194bce64ebfdfec4d67422bafac4595a6662b4f45f468`. Título interno: **FRcaixinha 2.2 — Contrato Técnico Mestre — Cláusulas Originais**. O texto registra aprovação em 16/10/2026, seções 1–16 e cenários AT-01 a AT-50 na seção 16. O `Caderno Mestre — Regras e Cláusulas — Texto Original` é outro PDF rastreado neste app, rotulado no nome como “147 cláusulas”; não foi feita contagem independente dessa cifra. Não foi encontrado anexo separado na árvore rastreada; os cenários AT integram o contrato. Foram extraídos para leitura com `pdftotext`; os PDFs não foram modificados.

O contrato exige Flutter/FastAPI/PostgreSQL (1.8), backend como fonte de verdade (2.9), primeiro período Price proporcional (8.4–8.5), Pix provado e conciliado (9), Capital-Dias diário (10.3) e segurança/backup (13). O README descreve sistema completo e failover WORM; as telas reforçam essas afirmações. O código é um demonstrador local React/Capacitor. A diferença entre contrato, README, interface e execução deve permanecer explícita.

### Matriz contrato × código × CI

| ID/cláusula | Requisito | Evidência no código | Teste/CI | Status | Severidade | Pendência |
|---|---|---|---|---|---|---|
| 1.5/1.8 | Android com backend autoritativo | `android/app/build.gradle:1`; `src/services/store.ts:589` | Build Android; sem teste de API | PARCIAL | ALTO | Backend, banco e contratos de API ausentes |
| 2.3/2.9/13.1 | Identidade autenticada e RBAC no servidor | `src/components/Navbar.tsx:221`; `src/services/store.ts:678` | Lint/build não validam autorização | NÃO IMPLEMENTADO | CRÍTICO | Autenticação, sessão e checagem por recurso |
| 2.7/6.2 | Membro vê apenas seus dados | `src/components/ContributionsView.tsx:42`; `src/components/LoansView.tsx:73`; `src/components/RaffleModuleView.tsx:83` | Sem teste de isolamento | CONTRADITÓRIO | ALTO | Filtros no servidor e correção das telas globais |
| 3.2/3.8 | Licença, preço, vigência e suspensão | `src/services/store.ts:300`; `src/services/store.ts:1054` | AT-04 usa PASS fixo | PARCIAL | ALTO | Checkout/aceite/Pix e suspensão automática |
| 4.2/8.2 | Price parametrizado por tenant | `src/services/store.ts:183`; `src/services/financialEngine.ts:79` | Função calculada isoladamente | PARCIAL | MÉDIO | Limites, política e aceites no servidor |
| 6.1-A/6.2 | Convite, validação e aceite | `src/components/MembersView.tsx:37` | Sem teste de admissão | CONTRADITÓRIO | ALTO | Tela cria usuário ativo e e-mail verificado sem prova |
| 6.4/7.2 | Contribuições e ledger conciliados | `src/services/store.ts:747` | AT-12 verifica apenas seed | PARCIAL | ALTO | Confirmação externa e ledger transacional |
| 8.4–8.5 | Primeiro período proporcional e datas pós desembolso | `src/services/financialEngine.ts:95`; `src/services/store.ts:818` | Exemplo padrão Price PASS | CONTRADITÓRIO | ALTO | Simulação e pedido usam datas/modos diferentes |
| 2.5/8.8 | Consentimento revalidado até o Pix | `src/services/store.ts:806`; `src/services/store.ts:889` | AT-08 PASS fixo | PARCIAL | ALTO | Revalidar na aprovação, reserva e envio |
| 9.2–9.8 | Pix real somente após autorização e conciliação | `src/components/PixModal.tsx:33`; `src/services/store.ts:889` | AT-11 PASS fixo | NÃO IMPLEMENTADO | CRÍTICO | Integração homologada, idempotência e reconciliação |
| 10.3–10.6 | Capital-Dias diário e fechamento conciliado | `src/components/CycleClosingView.tsx:55`; `src/components/CycleClosingView.tsx:86` | AT-14 testa só divisão de centavos | CONTRADITÓRIO | ALTO | Histórico diário e snapshot com pendências |
| 13.1–13.4 | Proteção de dados, backup e recuperação | `src/services/store.ts:655` | Nenhum teste de restauração real | NÃO IMPLEMENTADO | CRÍTICO | Servidor, criptografia, backup e ensaio |
| 13.5/infra | Métricas e nuvem verificáveis | `src/services/multiCloudService.ts:28`, `:170`, `:217` | Sem integração OCI/GCP | CONTRADITÓRIO | ALTO | Rotular simulação e validar infraestrutura real antes de alegá-la |
| 14.5–14.6 | Bolões apenas demonstrativos, sem cobrança | `src/components/BolaoModuleView.tsx:191`; `src/services/store.ts:1412` | Sem teste de bloqueio operacional | CONTRADITÓRIO | ALTO | Bloqueio e indicação inequívoca de simulação |
| 1.6/14.6 | Rifa privada fora do escopo aprovado | `src/components/RaffleModuleView.tsx:46`; `src/services/store.ts:1175` | Sem teste | CONTRADITÓRIO | ALTO | Decisão contratual formal antes de uso |
| 16.4 | AT-01–50 com provas reais | `src/services/auditRunner.ts:77`, `:137`, `:150` | Não é script de CI | CONTRADITÓRIO | ALTO | Substituir textos PASS por testes de comportamento em etapa futura |

## Fluxos e achados priorizados

1. **CRÍTICO — identidade e autoridade.** O menu permite escolher Master, administradores e membros de dois tenants sem credencial (`Navbar.tsx:221–361`). `switchContext` aceita os argumentos e persiste o estado (`store.ts:678`), sem conferir `roleGrants`. O servidor não existe; ocultar abas é apenas controle visual. Todo o estado de todos os tenants chega ao navegador (`store.ts:611`). Isto viola 2.3, 2.7, 2.9 e 13.1.
2. **CRÍTICO — pagamentos e saldos locais.** `PixModal.tsx:33–54` monta string ilustrativa e usa `setTimeout` para chamar a mutação local. `store.ts:747`, `:889`, `:934` alteram contribuições, empréstimos e ledger sem provedor; não há autorização do servidor. O botão de webhook duplicado não chama webhook. A tela chama “Mercado Pago • Pix Oficial Integrado”, gerando impressão falsa de operação real. Viola 9.2–9.8.
3. **CRÍTICO — proteção e persistência.** `store.ts:589,655` lê e escreve todo o estado, inclusive CPF, contatos, dívidas, saldos e atos, em `localStorage`. `addAudit` usa referência aleatória sem hash criptográfico (`store.ts:691`). Não há criptografia, imutabilidade, backup ou restauração autoritativa. Viola 12/13.
4. **ALTO — isolamento entre caixinhas.** Contribuições e empréstimos usam filtros visuais por tenant e membro, mas não há defesa por API. Rifas/bolões selecionam campanhas globais sem filtro de tenant (`RaffleModuleView.tsx:82,267`; `BolaoModuleView.tsx:84,297`); o roteiro do bolão mostra sempre `tenants[0]` (`BolaoModuleView.tsx:1059`). Master também pode abrir essas telas (`App.tsx:134`). Dados de outras pessoas podem aparecer em contexto indevido.
5. **ALTO — empréstimo e consentimento.** `LoansView.tsx:61` simula opcionalmente período proporcional, mas `requestLoan` em `store.ts:818` recalcula com a data atual e modo padrão; `approveLoan` e `disburseLoanPix` em `:880,889` não revalidam unanimidade. Membro de outro tenant pode ser encontrado por ID em `:799` sem checar `tenant_id`. Reserva atômica e Pix externo não existem.
6. **ALTO — fechamento.** `CycleClosingView.tsx:55` multiplica o total pago por 365, sem série diária nem reversões. Inicializa “APROVADO_PARA_LIQUIDACAO” e marca “FECHADO” após confirmação simulada (`:37,86`), sem verificar dívidas ou conciliação. Viola 10.1–10.6.
7. **ALTO — evidências falsas.** `auditRunner.ts:137,150,163` e várias outras entradas retornam `PASS` constante alegando backend, API 403 e idempotência inexistentes; `SupportSessionView.tsx:43` exibe resultados de webhook como strings fixas. Essas telas não são testes automatizados do produto.
8. **ALTO — nuvem.** `multiCloudService.ts:28–38` fixa RPO/RTO, latência e contagens; `:170` muda objeto em memória; `:217` gera “hash” por `Math.random`. `MultiCloudView.tsx:69` declara operação ativa. Não há OCI/GCP, replicação, WORM ou prova criptográfica; o contrato 13.4 define metas diferentes e condicionais.
9. **MÉDIO — cadastro e licenciamento.** `MembersView.tsx:37–78` cria adesão ativa e e-mail verificado sem confirmação, altera arrays diretamente e chama `addAudit` sem `persist`, de modo que a inclusão pode não sobreviver a recarga. Limites do plano e CPF não são validados nesse método. Preços podem ser alterados no estado local; a licença seed é tratada como ativa sem cobrança verificada.
10. **MÉDIO — textos e navegação.** “Taxa ZERO” (`LoansView.tsx:201`) significa taxa adicional zero, enquanto a mesma tela mostra juros de 20% a.m. (`:314`); rótulo ambíguo, não erro da fórmula. `AdminManualModal.tsx` contém 18 passos mas navegação limita a 16. `GitHubSyncModal.tsx` aceita PAT em estado React e declara sucesso simulado sem fazer push. Links ZIP em `MobileInstallModal.tsx` apontam para arquivos não rastreados.
11. **BAIXO/NÃO VERIFICÁVEL — layout móvel.** A tabela Price está em `overflow-x-auto` (`LoansView.tsx:360`), com cinco colunas sem largura mínima; o corte relatado pode ser rolagem horizontal e requer teste no aparelho. O dock é fixo (`App.tsx:307`) e o contêiner usa `pb-16` (`:162`); sobreposição real, safe area e teclado não foram medidos.

### Cálculo do exemplo Price

`PMT = 500 × [0,20 / (1 − 1,20^(−5))]`; `roundCents` usa `Math.round` de Number, não `Decimal ROUND_HALF_UP` contratado. Execução isolada de `calculatePriceSimulation` com 500, 20% a.m., 5 parcelas e modo de meses completos:

| Parcela | Juros | Amortização | Prestação | Saldo |
|---:|---:|---:|---:|---:|
| 1 | 100,00 | 67,19 | 167,19 | 432,81 |
| 2 | 86,56 | 80,63 | 167,19 | 352,18 |
| 3 | 70,44 | 96,75 | 167,19 | 255,43 |
| 4 | 51,09 | 116,10 | 167,19 | 139,33 |
| 5 | 27,87 | 139,33 | 167,20 | 0,00 |
| Total | 335,96 | 500,00 | 835,96 | 0,00 |

Os totais da função e do README coincidem: quatro parcelas de R$ 167,19 e última de R$ 167,20. A diferença de R$ 0,01 é ajuste final correto sob o modelo calculado. A divergência contratual é usar por padrão períodos mensais completos e não vincular o primeiro intervalo à data efetiva de liberação (8.4–8.5). “Taxa ZERO” é problema de rótulo; os juros não são zero. A frase “rendimento líquido” na UI não desconta despesas ou perdas e não comprova lucro líquido distribuível.

## Verificações e limites

| Ambiente/comando | Saída | Duração aproximada | Resultado |
|---|---:|---:|---|
| Termux `git ls-remote origin refs/heads/main` | 0 | 0,9 s | PASS; SHA confirmado |
| Termux `sha256sum` dos dois APKs | 0 | <1 s | PASS; cópias idênticas |
| Termux `aapt2 dump badging app-debug.apk` | 0 | <1 s | PASS; pacote/SDK/debug |
| Termux `unzip -p ... index-46h2HVbK.js \\| sha256sum` | 0 | <1 s | PASS; bundle igual a `dist/` |
| Termux `npm run lint` | 1 | 0,9 s | FAIL ambiental: falta `@typescript/typescript-android-arm64` no `node_modules` local |
| Termux execução isolada de `calculatePriceSimulation` | 0 | 0,8 s | PASS para o exemplo de meses completos |
| GitHub Actions web: `npm ci`, `npm run lint`, `npm run build` | 0/0/0 | 7/1/1 s | PASS na primeira execução |
| GitHub Actions Android: `npm ci`, `npm run build`, `npx cap sync android` | 0/0/0 | 6/<1/1 s | PASS na primeira execução |
| GitHub Actions Android: `./gradlew testDebugUnitTest assembleDebug` | 0 | 75 s | PASS; teste Java de template e APK debug compilado |

Execução Actions: https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41167414991. Nenhum APK foi publicado como artefato. O build web não é build APK. `git diff --cached --check` acusou espaços e CRLF do template Android gerado; não foram alterados para manter fidelidade à árvore local.

Escopo aberto/varrido: `README.md`, manifests/lockfiles, os dois PDFs em `public/assets/aistudio/`, `index.html`, `src/App.tsx`, `src/main.tsx`, `src/index.css`, `src/types/index.ts` por referências de tipos, todos os caminhos de `src/components/` e `src/services/` por leitura ou busca estática, `public/sw.js`, `public/manifest.webmanifest`, `capacitor.config.ts`, Gradle/manifest nativos e assets empacotados selecionados. Inspeção detalhada concentrou-se nos fluxos financeiros, permissões e nuvem; arquivos grandes de tela e seed tiveram leitura amostrada/por busca, não inspeção linha a linha integral. Fora: `node_modules/`, caches Gradle, binários PNG/JAR em conteúdo, `dist/` minificado além dos hashes, recursos Android gerados/ignorados, conteúdo de `local.properties`, e testes funcionais no aparelho. Não foi feita análise de código de dependências vendorizadas nem validação de serviço externo.

## Sincronização, pendências e próximo ciclo de testes

O commit de sincronização contém somente a árvore local necessária ao build e o workflow de auditoria. Foram preservados todos os arquivos exclusivos da `main`, incluindo `bun.lock`, PDFs e fontes. Foram excluídos `node_modules/` (dependências reinstaladas por `npm ci`), `android/.gradle/`, `android/build/`, `android/app/build/` e APK (gerados), `android/local.properties` (caminho de SDK local), `android/app/src/main/assets/` e configurações geradas por `cap sync`, e a cópia de Downloads (artefato local). `dist/` foi incluído porque o APK local embute esse bundle; assets antigos substituídos constam como exclusões no diff. Nenhuma fonte `src/`, contrato, tela ou regra financeira foi editada para o build.

Prioridade de correção futura, fora desta branch: (1) autenticação, autorização de backend e isolamento por tenant; (2) Pix real somente após homologação, conciliação e idempotência; (3) banco/ledger imutável lógico, privacidade e backup; (4) consistência Price/consentimento/fechamento; (5) delimitação de rifas/bolões e linguagem demonstrativa; (6) testes AT reais; (7) layout móvel e textos.

Sequência sugerida para testes no celular, **sem executá-los agora**: registrar dispositivo/largura e versão do APK; verificar a troca livre de papéis sem usar dados reais; conferir o que cada perfil vê em caixinhas distintas; observar a tabela Price e o dock com rolagem/teclado; comparar simulação e pedido no primeiro período; percorrer Pix apenas em modo demonstrativo, sem confirmar operação real; revisar rifas/bolões e telas de nuvem com atenção aos rótulos; testar persistência local com dados fictícios e recarga; registrar capturas e passos para cada discrepância.

Após a sincronização, a fonte canônica de código é o HEAD da branch `audit/termux-apk-20261031` até revisão da PR, **sem merge na main**. Para manter o Termux alinhado: `git fetch origin`, `git switch audit/termux-apk-20261031`, `git status` e `git rev-parse HEAD`; só editar depois de confirmar o SHA e preservar mudanças locais. O AI Studio não foi sincronizado diretamente: manter o export como referência visual, exportar futuras alterações para uma nova branch e comparar o diff antes de substituir código. Não editar em paralelo uma cópia antiga do AI Studio como se fosse a origem canônica.

Não foram feitas correções funcionais, operações financeiras reais, deployment, criação de nuvem paga ou merge em `main`. Para revisão no ChatGPT, trazer este relatório, o link da PR, os dois jobs Actions e os logs de qualquer falha Android, além do SHA do commit final da branch.

## Resultado final do CI e inventário exato da sincronização

A execução 41167414991 terminou com conclusão **success**. Web: `npm ci`, `npm run lint` e `npm run build` passaram. Android: `npm ci`, `npm run build`, `npx cap sync android` e `./gradlew testDebugUnitTest assembleDebug` passaram; o último passo levou cerca de 75 s. O teste Java é o exemplo gerado pelo template Capacitor, sem cobertura das regras financeiras. Não há artefato publicado.

Jobs: [web](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41167414991/job/124437875896) e [Android](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41167414991/job/124437875902).

Arquivos do primeiro commit de sincronização (A = adicionado; M = modificado; D = excluído):

```text
A	.github/workflows/audit-build.yml
A	android/.gitignore
A	android/app/.gitignore
A	android/app/build.gradle
A	android/app/capacitor.build.gradle
A	android/app/proguard-rules.pro
A	android/app/src/androidTest/java/com/getcapacitor/myapp/ExampleInstrumentedTest.java
A	android/app/src/main/AndroidManifest.xml
A	android/app/src/main/java/com/fronassor/frcaixinha/aistudio/MainActivity.java
A	android/app/src/main/res/drawable-land-hdpi/splash.png
A	android/app/src/main/res/drawable-land-mdpi/splash.png
A	android/app/src/main/res/drawable-land-xhdpi/splash.png
A	android/app/src/main/res/drawable-land-xxhdpi/splash.png
A	android/app/src/main/res/drawable-land-xxxhdpi/splash.png
A	android/app/src/main/res/drawable-port-hdpi/splash.png
A	android/app/src/main/res/drawable-port-mdpi/splash.png
A	android/app/src/main/res/drawable-port-xhdpi/splash.png
A	android/app/src/main/res/drawable-port-xxhdpi/splash.png
A	android/app/src/main/res/drawable-port-xxxhdpi/splash.png
A	android/app/src/main/res/drawable-v24/ic_launcher_foreground.xml
A	android/app/src/main/res/drawable/ic_launcher_background.xml
A	android/app/src/main/res/drawable/splash.png
A	android/app/src/main/res/layout/activity_main.xml
A	android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml
A	android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml
A	android/app/src/main/res/mipmap-hdpi/ic_launcher.png
A	android/app/src/main/res/mipmap-hdpi/ic_launcher_foreground.png
A	android/app/src/main/res/mipmap-hdpi/ic_launcher_round.png
A	android/app/src/main/res/mipmap-mdpi/ic_launcher.png
A	android/app/src/main/res/mipmap-mdpi/ic_launcher_foreground.png
A	android/app/src/main/res/mipmap-mdpi/ic_launcher_round.png
A	android/app/src/main/res/mipmap-xhdpi/ic_launcher.png
A	android/app/src/main/res/mipmap-xhdpi/ic_launcher_foreground.png
A	android/app/src/main/res/mipmap-xhdpi/ic_launcher_round.png
A	android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png
A	android/app/src/main/res/mipmap-xxhdpi/ic_launcher_foreground.png
A	android/app/src/main/res/mipmap-xxhdpi/ic_launcher_round.png
A	android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png
A	android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_foreground.png
A	android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_round.png
A	android/app/src/main/res/values/ic_launcher_background.xml
A	android/app/src/main/res/values/strings.xml
A	android/app/src/main/res/values/styles.xml
A	android/app/src/main/res/xml/file_paths.xml
A	android/app/src/test/java/com/getcapacitor/myapp/ExampleUnitTest.java
A	android/build.gradle
A	android/capacitor.settings.gradle
A	android/gradle.properties
A	android/gradle/wrapper/gradle-wrapper.jar
A	android/gradle/wrapper/gradle-wrapper.properties
A	android/gradlew
A	android/gradlew.bat
A	android/settings.gradle
A	android/variables.gradle
A	capacitor.config.ts
A	dist/assets/index-46h2HVbK.js
A	dist/assets/index-DA2Z8uu2.css
D	dist/assets/index-DN063-Ru.css
D	dist/assets/index-De_mXck2.js
M	dist/index.html
A	package-lock.json
M	package.json
```

PR aberta em modo rascunho, sem merge: https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/pull/1. O commit `8b2faa20c6189dcfdc38c63a2a0759d6b6847064` é o snapshot sincronizado da árvore que gerou o APK; commits posteriores nesta branch alteram apenas este relatório.
