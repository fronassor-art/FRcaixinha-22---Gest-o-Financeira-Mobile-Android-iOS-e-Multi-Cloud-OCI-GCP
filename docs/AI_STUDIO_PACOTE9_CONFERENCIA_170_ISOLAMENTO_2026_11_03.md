# Pacote 9 — Reforço da leitura isolada após a vistoria APK 170

## Checkpoint de origem
- APK 170 build ref 8b868861d182fca5111462fd2d72f44d26090ddc.
- Termux FASTAPI /api/health=200, /api/health/ready=200,
  /api/v1/auth/status=200, /api/v1/master/owner-access sem token=401.
- Capturas do Master, Admin, Membro, contribuições e empréstimos:
  homologação VISUAL OK. Execução de botões, revogação e testes
  cruzados NÃO foram comprovados apenas pelas imagens.
- Branch atualizacao-ai-studio-9b46a63187, PR #2 Draft.

## Entrega
1. Parser estrito do resumo de caixinha do PostgreSQL:
   source, tenant, papel, contagens não negativas, status não financeiro.
   A resposta Membro com contagem administrativa é recusada.
2. Parser estrito de membros: UUID, datas, duplicidade e campos privados.
   O cliente descarta CPF, e-mail, telefone e saldos inesperados.
3. O serviço de consultas impede chamar painel de tenant no contexto
   Master e impede a lista de membros no contexto Membro ou tenant alheio,
   antes de enviar o HTTP. Isso é defesa adicional à API e ao RLS.
4. Testes TypeScript negativos para três perfis, tenant cruzado, dados
   malformados e respostas com elementos privados.
5. Ampliação do teste Python com contas/caixinhas sintéticas no
   PostgreSQL descartável: GET dashboard e members, Master bloqueado,
   Membro sem contagem admin, e Admin apenas na caixinha própria.

## Restrições
- Não foi mudada nenhuma migration, GRANT, RLS ou dado financeiro real.
- Não emite convite, altera memberships ou habilita cobranças/Pix.
- O PostgreSQL e a autenticação do FastAPI seguem autoridade final.
- Sem APK manual até o próximo checkpoint planejado 180, salvo
  regressão crítica de segurança. CI compila APK em cada pacote.
