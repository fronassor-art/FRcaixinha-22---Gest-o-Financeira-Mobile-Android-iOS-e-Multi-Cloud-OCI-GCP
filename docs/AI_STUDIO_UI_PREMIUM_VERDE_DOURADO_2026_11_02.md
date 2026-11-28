# FRcaixinha AI Studio — visual premium verde e dourado

Checkpoint de redesign visual solicitado por referência do proprietário.
Escopo exclusivo no repositório AI Studio (PR #2, Draft).

## Sistema visual
- Paleta: verde-floresta e esmeralda; dourado nos destaques e botões;
  fundo creme para cartões de leitura.
- Novo ícone **SVG original inspirado** na referência: monograma dourado
  com folhas verdes; ícone adaptativo Android em VectorDrawable, com
  versão simplificada por legibilidade em tamanho pequeno.
- Splash nativo configurado com fundo verde e o mesmo monograma Android.
- Login: marca centralizada, e-mail e senha, botão Entrar dourado,
  aba Primeiro acesso (membro/administrador informativo, sem auto-registro).
- Tela principal: cabeçalho leve, contexto autorizado apresentado em
  cartões Master/Admin/Membro; menu inferior com Início, duas áreas
  específicas por papel e Mais.
- Dashboard: hero esmeralda e cartões de dados reais lidos da API, sem
  saldos, metas ou progresso de demonstração que pareçam confirmados.
- Ferramentas técnicas disponíveis apenas no contexto Master.
- Build SHA visível para identificar qual APK está realmente instalado.

## Segurança e limites
O visual nunca substitui as verificações de API, RLS e senha; a troca
de perfil usa switchContext validado no servidor. Os caminhos para primeiro
acesso informam necessidade de convite/autorizações; nenhum cadastro
público nem biometria foi habilitado. Não exibe balanços fictícios,
não habilita Pix, pagamentos reais ou rifas. Sem alterações em SQL,
dados reais, identidade Master ou conta de membro. Aplicação no aparelho
requer download do novo APK e teste dos três perfis.

## Controle de qualidade
CI valida lint, regressões de login e troca de contexto, compatibilidade
PostgreSQL e novo teste de branding. Apk deve ter icon adaptativo
FRcaixinha e build id correspondente ao commit validado.
