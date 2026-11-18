# FR Finance M40420 — apresentação de campanhas no Android

Após M40410, foi identificada a necessidade de validar respostas recebidas
da API antes de apresentá-las como campanhas ou oportunidades.

Este pacote incorpora parser de falha fechada para oportunidades, campanhas
e preferências. Dados inválidos, valores não monetários, status desconhecidos,
UUIDs incorretos, destinatários duplicados ou indicações de entrega externa
são rejeitados; a interface não deve mostrar oportunidade inventada.
Os status INTERESTED/DECLINED/PENDING passam a aparecer em português.
Ofertas vencidas não exibem ações de interesse nem simulação.
Mensagens de sucesso de uma operação não são apagadas automaticamente
pelo recarregamento decorrente da própria operação (mas mudança de contexto
continua limpando a mensagem anterior).

CI: validações offline do parser e renderização inicial SSR da interface
para os perfis Master, Admin e Membro; a CI geral compila novo APK assinado.
Isso não substitui os testes físicos no Android.

Sem alteração de endpoints, migrations SQL, autenticação, produção ou gates.
FR_FINANCE_SPECIAL_CREDIT_SANDBOX permanece NO no dispositivo.
PIX, pagamentos, e-mail, push, WhatsApp, SMS reais OFF. PR #2 Draft.