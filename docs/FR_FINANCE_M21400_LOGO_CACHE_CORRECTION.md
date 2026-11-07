# FR Finance M21400 — logotipo e invalidação de cache

O proprietário confirmou nas capturas do APK M21300 que o texto do aplicativo e o cabeçalho já mostram FR Finance, mas o grande logotipo do login ainda pode mostrar FRcaixinha.

Diagnóstico reproduzível: o APK M21300 possui `assets/public/icon.svg` com texto FR Finance, porém `assets/public/sw.js` ainda contém `CACHE_NAME='frcaixinha-v2.2-cache'` e uma estratégia stale-while-revalidate para SVG, podendo entregar o recurso antigo na primeira exibição.

Correções:
- Mudança do nome do cache de recursos para M21400 (limpeza de caches antigos na ativação do SW).
- Caminho de logo com query de versão em LoginView, Navbar, favicon e manifesto PWA.
- Requisição do logotipo no service worker é network-first, com fallback somente ao mesmo recurso em cache quando offline.
- Mantidos todos os controles, login, sessions, banco 46 tabelas, 044, headers, paths técnicos, assinatura e identificadores Android. Nenhuma migração.
- O uso da palavra "caixinha" em botões como nome da unidade financeira é distinto do nome comercial; logo e marca devem ser FR Finance.
- Homologar atualização por cima da versão M21300, sem apagar dados. Conferir arte do login e cabeçalho.
