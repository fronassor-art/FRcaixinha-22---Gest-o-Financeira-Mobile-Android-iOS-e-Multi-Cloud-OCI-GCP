# Macropacote 160 — consultas financeiras em homologação
Data: 03/11/2026. Baseline: 3755a75f1a6618c16e03f391d8a99dccc3ead630 (CI #199).

Somente leitura, sem migrações, operações reais, novos bancos ou segundo backend.
Acesso entre tenants e Master continua bloqueado no FastAPI e pelo PostgreSQL RLS.
Os dados sintéticos dos testes não são usados como pagamentos ou receita real.

20 verificações de frontend: 5 valores válidos (contagens, devido, pago, pendente);
2 bloqueios tenant/ano; 3 bloqueios source/resultado/lucro; 5 bloqueios de
valores e contagens inconsistentes; 5 rejeições de campos extras ou privados.

Backend: leitura exclusiva de Membro ou Administrador; 6 cenários de
acesso negado sem consulta SQL; 16 cenários de montantes/contagens inválidos
recusados HTTP 503; consulta SQL somente SELECT por tenant, vínculo e ano.

A tela descarta respostas de sessão antiga, atualiza sem mostrar o dado
anterior e declara que registro pago não equivale a conciliação bancária.

Critérios de aceite: CI 6/6 PASS + APK atualizado com SHA conferido + testes
de Master/Admin/Membro, valores 2027 e falha de rede no celular.
**Não** concluir os 20 itens apenas porque CI compilou APK.
Pendências globais: inventário de instâncias do Termux, mais testes em produção
segura, integração Mercado Pago e liberação contratual de operações financeiras.
