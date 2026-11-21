# FR Finance M37450 — licença do tenant original, diagnóstico read-only

M37449 confirmado no smartphone: sem ciclo aberto, prévia 2027 R$150
com servidor autenticado, FastAPI online, nenhum efeito financeiro.
A tela de Master continua mostrando "Sem licença confirmada no PostgreSQL".

Este pacote investiga o **estado persistido de licenciamento**, sem
forjar pagamentos ou presumir licença apenas porque um plano existe.

SELECT no PostgreSQL 18 original (frcaixinha_aistudio_dev, 5433):
conta plans/price versions, preparações de assinatura, intents de
pagamento, registros aprovados, entitlements presentes/ativos, direitos
em vigência na caixinha ativa, inconsistências cross-tenant e RLS FORCE.
Verifica que app/auth não possuem INSERT/UPDATE de licença/pagamento.
Também confirma ausência de ciclos, contribuições, Pix e ledger.

Nenhum valor ou ID sensível, token, CPF ou e-mail é exibido.
Nenhuma consulta ao provedor Mercado Pago ocorre — um registro
"APPROVED" no banco não prova cobrança reconciliada.
Nenhum usuário é ativado e a saída nunca declara produção autorizada.

O M37450 também pode encontrar preparações/entitlements antigos.
Nesse caso o relatório traz contagens e exige revisão específica;
não altera estado nem concede direito comercial.

Testes CI sintéticos cobrem ausência de licença, entitlements registrados
sem comprovação bancária, RLS/privilégios, contagens e identidade PG18.
A execução local de leitura é separada da homologação GitHub 6/6.
