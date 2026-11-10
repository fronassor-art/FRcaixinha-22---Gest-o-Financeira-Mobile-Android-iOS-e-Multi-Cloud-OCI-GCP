# FR Finance M37451 — Master não pode apresentar cobrança fictícia

M37450 foi auditado no PostgreSQL original: 3 planos, 2 versões de
preço, 0 preparações, 0 pagamentos e 0 licenças. Não existe data
contratual de vigência ou pagamento reconciliado.

A tela Master ainda mostrava "Valor Pro-Rata Devido" calculado com
R$89,90 / R$109,90 e datas estáticas de 2026/2027, o que podia ser
interpretado incorretamente como cobrança ou valor contratual.

M37451 troca a simulação por uma comparação informativa da diferença
mensal obtida EXCLUSIVAMENTE dos preços atuais do catálogo PostgreSQL.
Não mostra vencimento, dias restantes ou valor de cobrança quando não
há licença com datas comprovadas. Declara que um cálculo operacional
exige assinatura, datas reais e pagamento verificado.

Mantém os controles de RLS, de não abertura de ciclo e de Pix real OFF.
Não grava licenças, não registra pagamentos, não cria usuários e não
altera o banco local. O APK anterior permanece funcional; a interface
revisada requer uma nova compilação para refletir o texto.

A ativação real de SaaS permanece dependente de onboarding com aceite
contratual, preparação versionada, provedor comercial, conciliação e
entitlement comprovado; estes requisitos não são substituídos por CI.
