# Pacote 25 — Barra de status e rolagem do Android (03/11/2026)

Escopo: UI Android/Capacitor e CSS. Nenhuma alteração em banco, FastAPI,
auth, permissões, licenças, Pix ou PR/main.

## Evidência de homologação
O usuário reportou relógio/bateria sobre o logo, seletor de perfil cortado
e rolagem da tela inteira. Nas capturas recebidas o cabeçalho ainda
mostrava 967947a, a versão do APK 191. No APK 193 CI o asset JS contém
6ad70cd. Portanto é obrigatória verificação do hash exibido no cabeçalho
após instalar o APK corrigido; não confundir Git HEAD no Termux com APK instalado.

## Ajustes
- Capacitor 8 SystemBars: insetsHandling=css. As variáveis
  --safe-area-inset-* são fornecidas pelo plugin e o CSS usa env() como fallback.
- Document/body não recebem rolagem; #root é posicionado em viewport fixa e
  recebe safe-area superior uma única vez.
- Header e barra de perfil não pertencem ao elemento com overflow-y:auto.
- Rodapé permanece fixo na casca flex; conteúdo central tem scroll próprio.
- Texto do perfil pode quebrar em mais de uma linha, sem ocultar a identificação.
- Login conserva rolagem interna para dispositivos pequenos.
- CI verifica CSS, markup e configuração nativa. Isso NÃO substitui teste
  visual do APK em um aparelho Android 17.

## Homologação manual
Instalar APK de novo build **por cima** da versão anterior; confirmar o novo
SHA de sete caracteres no cabeçalho. Percorrer Início, Licenças, Administradores,
Fechamento e Meu Resultado. Arrastar para cima/baixo 5 vezes; checar relógio,
ícones, logo, descrição do perfil, botão Sessões, rodapé e campo de busca
com teclado aberto. Verificar orientações retrato/retorno e login/logout.
Se o SHA permanecer antigo, o APK novo não foi carregado: investigar
instalação, PackageId/assinatura e atividade, sem reinstalar apagando dados.
