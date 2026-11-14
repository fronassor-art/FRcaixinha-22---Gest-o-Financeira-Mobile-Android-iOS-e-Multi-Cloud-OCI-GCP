# FR Finance AI Studio — M28611: pesquisa de VPS 8 GB, pagamento baixo e continuidade do deployment

**Data-base:** 08/11/2026. Pesquisa pública informativa, sem acesso a checkout autenticado, cartão do operador, contas de provedores ou garantia de estoque. Preços/cotações são referências e precisam ser confirmados no checkout. Esta frente é **FR Finance AI Studio**, exclusivamente; a implantação OCI anterior permanece intacta.

## Requisitos fornecidos pelo proprietário

- Uma VPS Linux **8 GB RAM**, FastAPI + PostgreSQL + HTTPS + workers, operação prevista 24x7.
- Custo alvo até **R$120/mês** de preferência; não disponibilizar US$100 de limite no cartão apenas para cadastro/upgrade.
- Preferência por **pagamento de 1 mês por Pix**, sem pré-pagamento de 12/24 meses, verificando renovação.
- Preferência por datacenter brasileiro e suporte em português, com backup cifrado independente e restauração testada.
- Ainda não é operação bancária: ações Pix são executadas pelo provedor de pagamentos. Pix real e ativação de usuários permanecem OFF.

## Fontes primárias e preços vistos

| Provedor | Plano 8 GB | Condição/preço visto | Principal risco |
| --- | --- | --- | --- |
| **Hostinger** | KVM 2: 2 vCPU, 8 GB, 100 GB NVMe; Brasil na lista de VPS | Promo anunciada R$43,99/mês **no contrato de 24 meses pago integralmente**; preço mensal regular divulgado R$108,99 de referência; **selecionar explicitamente 1 mês no checkout**. Pix e boleto aceitos | Não confundir mensal equivalente com total do cartão. Backup semanal incluso, mas insuficiente sozinho |
| **KingHost** | VPS 8 GB: 6 vCPU, 170 GB SSD, datacenter Brasil | Promo R$63,90/mês equivalente no prazo longo; botão Mensal existe. Fonte comparativa de 31/10 indica R$103,90/mês, **mas fontes terceiras divergem, preço mensal oficial não confirmado**. Pix/boleto aceitos | confirmar preço real, backups, CPU compartilhada, acesso/root e termos antes de pagar |
| **Hospedagem Segura** | VPS Linux 8: 4 vCPU, 8 GB, 100 GB NVMe | R$119,90/mês, mensal sem fidelidade, Pix/boleto/cartão | backup não incluso, serviço deve ser diligenciado |
| **Hospede Aqui** | Cloud 8G: 4 vCPU, 8 GB, 100 GB | R$129,90/mês, Pix, sem fidelidade | acima do teto, domínio recente e reputação independente insuficiente |
| **Nice Hosting** | VPS Medium: 4 vCPU, 8 GB, 60 GB NVMe | R$99/mês anunciado | Reclame Aqui Detector (25/09/2026) indica ausência de CNPJ localizado e reputação insuficiente; não é candidato para dados reais sem diligência |
| **OVHcloud** | VPS 2027 VPS-2: 4 vCores, 8 GB, 75 GB NVMe, backup diário limitado | US$8,50/mês na tabela mundial de referência; ~R$47 ao câmbio de R$5,50/USD; valor real por conta/localização/impostos pode diferir | pagamento internacional/PayPal, custos e disponibilidade geográfica não confirmados para Brasil |
| **Contabo** | Cloud VPS 4: 4 vCPU, 8 GB, 100 GB SSD | Promo ~€4,40/mês por 24 meses (USD ~5,28), **não é mensal livre garantido**; cotações por prazo, setup/localidade precisam ser vistas no checkout | pré-pagamento, latência, backups e possíveis adicionais |
| **Hetzner** | CX33: 4 vCPU, 8 GB, 80 GB NVMe | €8,49/mês excl. IVA/IPv4 na UE após reajuste de 15/06/2026; rastreadores em novembro indicam **estoque indisponível** | não adequado à urgência até confirmar estoque |
| **IONOS** | VPS L+: 4 vCore, 8 GB, 240 GB NVMe | US$8/mês **só nos 3 primeiros meses do compromisso de 1 ano**; lista US$25/mês | promoção e compromisso não são custo estável |
| **DigitalOcean** | Basic: 4 vCPU, 8 GB, 160 GB SSD | US$48/mês | fora do orçamento |
| **Scaleway** | DEV1-L: 4 vCPU, 8 GB | €31,27/mês mais serviços/impostos | fora do orçamento |

Referência cambial informativa (nov/2026): USD ~R$5,50 e EUR ~R$6,14. Não inclui spread, IOF, tributos ou custos adicionais de backups.

## Recomendação condicionada

**1º:** confirmar no **carrinho oficial** KingHost *Mensal*, VPS 8 GB (não bienal), preço total de um mês, renovação, Pix, dados de região, backup, disponibilidade, cobrança de IP/tributos, SSH e Linux. Por reputação e localização brasileira é forte opção, **mas NÃO considerar R$103,90 comprovado até o checkout**.

**2º:** Hostinger KVM 2 selecionando *1 mês*, com referência de renovação R$108,99 e pagamento Pix; confirmar que datacenter Brasil está disponível para VPS específica. Não usar a oferta promocional de R$43,99/mês como se permitisse pagar R$43,99 isoladamente.

**3º:** OVHcloud VPS-2 se houver método de pagamento acessível, checkout claro e localização/latência aceitável; backup da oferta não substitui backup independente PostgreSQL.

Não se encontrou evidência de uma autorização universal de **US$100** nesses provedores semelhante à atualização Oracle PAYG, mas não é possível garantir ausência de validações temporárias do cartão. **Pix de preço fechado** evita necessidade de cartão para o pagamento se o checkout permitir a operação.

## Plano técnico para não bloquear o FR Finance

1. Contratar **um mês apenas**, depois de validar checkout e titularidade (apenas proprietário autoriza compra). Não criar conta/provisionar máquinas automaticamente.
2. VM Ubuntu 24.04 LTS ou Debian 12/13 em x86_64/ARM64 conforme provedor, root SSH por chave, firewall portas 80/443 e SSH restrito; PostgreSQL **somente loopback/rede privada**.
3. Configurar FastAPI/ASGI, frontend Capacitor/web, PostgreSQL 18 (compatibilidade), serviço de e-mail transacional Brevo já homologado, reverse proxy HTTPS para `api.frfinance.com.br` e `app.frfinance.com.br`.
4. **Adaptar dependência OCI exclusiva**: há código `backend/app/oci_mp_staging_server.py` com instance principals/Vault OCI, que não poderá simplesmente rodar em VPS externa. Implementar uma interface de provedor de segredos com IAM/local secret store seguro, sem reusar senhas, segredos em APK ou logs. Manter OCI como alternativa futura sem misturar repositórios.
5. Testar restore de backup cifrado externo e Postgres RLS/roles, segurança Master/Admin/Membro, capacidade 24x7, filas de e-mail/webhooks em staging; habilitar usuários reais/MP/Pix **somente após gates explícitos**.

## Fontes consultadas

- Hostinger: https://www.hostinger.com/br/servidor-vps ; https://support.hostinger.com/pt/articles/1583236-quais-as-formas-de-pagamento-aceitas-pela-hostinger ; https://support.hostinger.com/en/articles/1583267-where-are-hostinger-servers-located
- KingHost: https://site.king.host/servidor-vps ; https://king.host/wiki/artigo/formas-de-pagamento/ ; https://www.reclameaqui.com.br/empresa/kinghost-hospedagem-de-sites/
- Comparação de KingHost 31/10/2026 (não oficial): https://selfhostbr.com/artigos/quanto-custa-hospedar-n8n/ ; também há fonte terceirizada divergente https://www.kompare.com.br/kinghost/servidor-vps/planos
- Hospedagem Segura: https://www.hospedagemsegura.com.br/vps/
- Hospede Aqui: https://hospedeaqui.cloud/contratar/vps
- Nice Hosting e diligência: https://www.nicehosting.com.br/vps.php ; https://www.reclameaqui.com.br/detector-site-confiavel/nicehosting.com.br
- OVHcloud: https://www.ovhcloud.com/en/vps/ ; https://www.ovhcloud.com/en/terms-and-conditions/payment/
- Contabo: https://contabo.com/en-us/vps/ ; https://help.contabo.com/en/support/solutions/articles/103000269311/
- Hetzner: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- IONOS: https://www.ionos.com/servers/vps.html
- DigitalOcean: https://www.digitalocean.com/pricing/droplets
- Scaleway: https://www.scaleway.com/en/pricing/virtual-instances/

**M28611 = RESEARCH_COMPLETE / PURCHASE_NOT_AUTHORIZED / ALL_REAL_FINANCE_OFF**.
