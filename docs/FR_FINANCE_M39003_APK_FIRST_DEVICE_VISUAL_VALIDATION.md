# FR Finance M39003 — primeiro teste visual no Android (capturas do usuário)

## Origem e limites

O APK homologação Android `com.frcaixinha.app.aistudio` versão `1.0.1080-AI-STUDIO-TEST` derivado do commit `237e1a5` foi **baixado, instalado e aberto no celular**. O usuário enviou **sete capturas reais de execução**, mostrando as rotas de entrada, Administração Master, Administração da caixinha e Membro. As capturas são evidências de **renderização e navegação visual**; **não provam** por si sós login real, RLS, identidade do servidor, operações financeiras, requisição autenticada, inscrição comercial ou entrega da Brevo. Não publicar os arquivos de imagem do usuário no repositório.

### O que foi visto nas capturas

1. Acesso: logo, perfis Administrador e Membro, aviso de API local e botão de diagnóstico.
2. Master, cadastro: navegação em Caixinhas com uma caixinha **Ativa** apresentada; aviso cadastral antigo dizia que convites aguardavam **implementação**.
3. Master, Licenças: editor do plano ESSENCIAL exibia mensalidade aproximada de R$ 50,00, anual calculado de R$ 500,00 e texto interno `LicensePriceVersion`. A regra visual **10 × mensalidade** estava consistente com o contrato de assinatura.
4. Administrador: painel com duas pessoas na caixinha e zero cotas/contribuições; sem prova de ciclo aberto ou cobrança.
5. Administrador, ciclo: mínimo **R$ 150,00 por cota**, valor por ciclo decidido pelo administrador, sem abertura de ciclo confirmada.
6. Membro: painel individual sem valores financeiros reais atribuídos.
7. Membro, contribuições: zero contribuições listadas, mensagem de Pix indisponível; não houve recebimento nem conciliação de pagamento.

### Ajustes M39003 implementados

- `src/components/MasterTenantRegistryView.tsx`: informa que convites/mudanças de acesso dependem de **verificação de identidade, contrato e aprovação operacional**; esta tela permanece **somente leitura** e não ativa contas. O texto anterior de funcionalidade inteiramente não implementada estava desatualizado após o desenvolvimento do outbox 047 e das funções 048, mas estas **não estão ativadas**.
- `src/components/MasterLicensingView.tsx`: liga o rótulo ao campo mensal com `htmlFor`/`id`, facilita teclado decimal, aceita precisão de **1 centavo** conforme o contrato `decimal_places=2` da API e deixa explícito que assinatura SaaS mensal **não é** contribuição dos membros, cujo piso por ciclo é R$ 150,00. Remove nome técnico de tabela/estrutura da informação ao usuário, sem alterar a versão imutável realmente persistida pelo servidor nem a regra anual `10 × mensalidade`.
- `src/tests/master_tenant_registry_ui.test.ts` atualizado; `src/tests/m39003_apk_ui_screenshot_regressions_ci.test.ts` e passo no GitHub Actions para impedir regressão de mensagens e limites comerciais.

### O que NÃO foi feito

- Não foram alterados backend SQL, pagamentos, banco 5433, a FastAPI local, OAuth, Brevo, assinatura APK ou código de autenticação.
- Nenhuma conta de usuário ou licença foi criada/alterada; nenhum Pix ou e-mail enviado.
- A correção está no **código-fonte**; só será visível no dispositivo **depois de compilada e instalada uma nova versão** com assinatura compatível.
- Ainda precisam de comprovação: botão de diagnóstico de API, login real por perfil (sessões distintas), escopo tenant/RLS, retomada após logout, fluxo de e-mail com HTTPS funcional, OAuth/Orders com provedor autenticado e APK release assinado.

**Status:** captura visual inicial favorável; homologação funcional de produção permanece **BLOQUEADA** até provas E2E.
