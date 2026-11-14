# M22500 — Painel Android: revisão do histórico abaixo de R$150

O administrador possui o botão Auditar competências antigas (somente leitura) na área Contribuições. A API requer TENANT_ADMIN do próprio tenant e consulta os grupos históricos sem mostrar membros ou CPFs. O frontend valida ciclo/tenant, contas em centavos, ausência de liquidação bancária e a proibição de ajustar qualquer obrigação.

A análise exibe quantidade, valor devido, pagamento cadastrado e saldo cadastral, com aviso de que não existe conciliação real. Não altera valor da cota, não gera Pix e não marca contribuições pagas. A tela descarta respostas caso o login mude enquanto a consulta estiver em andamento.

CI valida o parser e presença de fronteiras de sessão/perfil. Homologação no APK e aplicação da política administrativa de regularização continuam pendentes.
