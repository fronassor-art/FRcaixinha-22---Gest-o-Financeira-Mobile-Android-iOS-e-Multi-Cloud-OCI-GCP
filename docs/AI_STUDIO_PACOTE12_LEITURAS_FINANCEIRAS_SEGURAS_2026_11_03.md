# Pacote 12 — Leituras financeiras minimizadas / AI Studio Mobile

Checkpoint anterior: 4a77b77f7141e98fbd83f573dee24c5b4ea54cf7.
PR #2 Draft, branch atualizacao-ai-studio-9b46a63187.

## Mudanças
- Em fetchContributions, fetchLoans e simulateLoan, a sessão e
  o tenant solicitado são comparados ANTES de enviar HTTP.
- Master não consulta esses dados patrimoniais. Admin e Membro ficam
  limitados à própria caixinha. FastAPI e PostgreSQL RLS seguem autoritativos.
- Respostas de empréstimos são verificadas: tenant, IDs, datas,
  contagens, valores monetários e duplicidade de parcelas/empréstimos.
- Dados que o painel não necessita são omitidos. Respostas com
  credenciais, CPF, e-mail, conta bancária ou Pix inesperados são recusadas.
- A UI de empréstimos usa somente o modelo validado.
- Testes sintéticos exercitam Master/Admin/Membro, tenant alheio,
  payload malformado, dados privados e números não finitos.
- Nenhuma alteração no cálculo financeiro, no banco ou nas regras de negócio.

## Limites
A defesa é adicional ao RBAC/RLS. Não verifica por si só a identidade
do tomador do empréstimo em uma resposta Membro: isso depende do
PostgreSQL, vínculo de membership e contexto RLS da API.
Não habilita pagamento Pix, aprovação, desembolso, cobranças ou conciliação.
Sem migrations reais, grants, conta real, merge ou APK manual antes do 180.
