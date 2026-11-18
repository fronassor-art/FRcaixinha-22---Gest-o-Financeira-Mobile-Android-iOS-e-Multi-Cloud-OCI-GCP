# FR Finance M40500 — auditoria e pacote unificado Android

Checkpoint de entrada: M40440 e0d59d5 sincronizado; CI 7/7 PASS;
branch atualizacao-ai-studio-9b46a63187; PR #2 Draft.

## Cinco pendências e soluções entregues ao repositório

1. **Tela inicial encoberta pelo Android**. Causa encontrada:
   centralização vertical (justify-center) em área rolável com conteúdo
   maior que a viewport. Login passa a usar justify-start mais margens
   automáticas my-auto. Preserva safe-area CSS e barras do Android, permite
   voltar ao topo mesmo quando o teclado aparece.
2. **Ícone aparecendo apenas com a letra R**. SVG continha o texto R
   duplicado. Foreground adaptativo Android também era o monograma R.
   O pacote substitui pelo desenho FR, conserva o nome FR Finance e
   atualiza a versão do cache de ícones da interface/PWA.
3. **Biometria ausente**. Plugin nativo Android FRDeviceSecurity para
   detectar sensor disponível e biometria cadastrada, solicitar
   verificação biométrica e oferecer habilitação por conta. Quando
   ativada, a tela é bloqueada ao colocar o app em segundo plano;
   desbloqueio depende de biometria e de sessão ainda válida no servidor.
4. **Foto individual de administrador e membro**. Menu Meu perfil com
   seleção JPG/PNG/WebP, conversão no próprio WebView para JPEG compacto,
   exibição, troca e exclusão. Android Keystore AES-GCM armazena em
   arquivos privados identificados por hash da conta e caixinha;
   nenhuma foto é enviada à API.
5. **Nomes ausentes ou incorretos**. Navbar, faixa de perfil e
   DashboardView passam a usar o nome retornado pela autenticação do
   servidor, em vez das identidades fictícias do AppStore.

## Segurança, limites e privacidade

A biometria não efetua login nem substitui senha e RBAC/RLS; o
servidor FastAPI continua responsável por emitir, expirar e revogar
sessões. Depois de Sair da conta, é necessário digitar senha novamente.
Cancelar/falhar no desafio não desbloqueia o aplicativo. Não há
coleta de impressões digitais, imagens faciais ou credenciais.

A opção biométrica e a foto ficam apenas no Android. Uma foto não
sincroniza com outros celulares ou com a OCI. Desinstalar/limpar
dados do aplicativo remove a imagem e as preferências locais.
O Master não pode visualizar fotos de outra conta na interface.
O nome exibido é administrado pelo cadastro do servidor, não
pode ser falsificado pelo campo de edição de perfil.

O SVG, a tela de login e o foreground adaptativo usam o novo
monograma FR. Revisar também o ícone do launcher nos Android
antigos que ainda usam os PNGs legados.

Não foram acrescentadas migrations, alterações na API, conexões
ao PostgreSQL original do Termux (FR Finance 127.0.0.1:5433),
reinícios, PIX ou pagamentos reais. O banco separado do
FR Caixinha 2.2 permanece fora do escopo.

## Testes antes de liberar o APK

- CI: TypeScript, testes de layout Android, M21400 atualizado,
  M40500 consolidado, build web e APK debug assinado;
  backend/RLS só em PostgreSQL descartável na CI.
- Físico: tela inicial e retorno do logout sem cortar o logo,
  abrir teclado, alternar perfis e nomes do servidor.
- Físico: Android com biometria cadastrada, habilitar proteção,
  sair do aplicativo e retornar; cancelamento deve manter bloqueio.
  Sair e entrar com senha deve continuar funcionando.
- Físico: foto A salva, substituída, excluída e persistente;
  membro B sem ver a foto de A.
- Físico: biometria não disponível não pode gerar login falso.
- Confirmar Pix, pagamentos, comunicações e produção desativados.

Os testes estáticos e a CI não substituem a prova física do sensor.

PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF;
FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO; PRODUCTION=BLOCKED.
