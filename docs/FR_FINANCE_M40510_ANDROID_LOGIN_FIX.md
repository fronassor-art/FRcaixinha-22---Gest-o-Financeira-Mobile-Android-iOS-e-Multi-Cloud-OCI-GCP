# FR Finance M40510 — correção da falha física residual do M40500

## Evidência da homologação física

O usuário informou em 18/11/2026: **4/5 PASS, 1/5 FALHA**.
PASS: monograma FR, biometria no Android, foto separada por perfil,
nome autenticado. FALHA: topo da tela inicial/logotipo ainda pode ficar
encoberto, especialmente após sair da conta e ao abrir o teclado.

## Causa e correção

O M40500 já tinha alterado a centralização para justify-start,
mas o login permanece um contêiner com rolagem própria dentro de um
#root fixo, e o Android pode conservar scrollTop do WebView depois do
logout. Além disso, quando o teclado abre, a altura do visualViewport
pode ser menor que a área da janela usada por CSS 100dvh.

M40510 altera apenas a apresentação:
- Reseta explicitamente scrollTop/scrollLeft na montagem da tela, ao
  trocar modo e perfil e no próximo frame.
- Quando o usuário está no seletor inicial (sem teclado de entrada),
  uma mudança de altura/scroll visual ou pageshow retorna ao topo.
- Ajusta max-height do contêiner ao visualViewport real, respeitando
  a posição do elemento e o espaço restante do #root.
- Adiciona proteção de âncora (overflow-anchor:none) e padding superior
  no próprio login, mantendo o inset original do Android.
- Preserva rolagem necessária ao formulário de senha e primeiro acesso.

## Limites de homologação

A bateria M40510 cobre matematicamente variações de teclado, barras
do Android, viewport menor, logout, estrutura React/SSR e CSS. Isto
**não substitui** a observação no dispositivo real. A falha física
continua pendente até repetir os passos em novo APK e obter PASS.

Sem alterações no FastAPI, na API de autenticação, no plugin biométrico,
nas fotos criptografadas, no PostgreSQL original 5433, nem no FR Caixinha 2.2.
Sem migrations ou reinícios. `PIX_REAL=OFF`,
`PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`,
`PRODUCTION=BLOCKED`. PR #2 Draft.

### Reteste necessário no aparelho

1. Abrir APK e verificar o ícone FR, topo e tela completa.
2. Entrar e sair pelo botão do aplicativo: login deve voltar com
   logotipo integralmente visível, mesmo após rolar a tela antes de entrar.
3. Selecionar administrador/membro, focar email e senha, abrir e fechar
   o teclado Android: campos e botões acessíveis via rolagem.
4. Voltar ao seletor de perfil e abrir primeiro acesso sem corte do topo.
5. Manter biometria, foto, nomes e bloqueio financeiro conforme PASS M40500.
