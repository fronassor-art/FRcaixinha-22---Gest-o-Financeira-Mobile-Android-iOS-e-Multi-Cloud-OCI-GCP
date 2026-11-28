# FR Finance M40930 — handoff documental de staging e Mercado Pago (SEM ATIVAÇÃO)

20/11/2026. Documento de preparação, **não** provisiona OCI, provedor, domínio, banco ou credenciais. Prioridade de P0 continua sendo M40570/M40730, identidade SQL e custódia Master; M40840 e M40930 permanecem NO-GO.

## Staging: checklist de evidência a produzir

| Área | Estado não atestado | Evidência exigida |
|---|---|---|
| Compute | OCI A1 com histórico de `OUT_OF_HOST_CAPACITY`, sem VM staging comprovadamente disponível neste checkpoint | OCID e shape de host isolado, plano/preço verificado, região, imagem, UID de serviço, atualizações e execução monitorada. VPS alternativo somente por aprovação de custo. |
| Rede | VCN e subnet previamente planejadas; HTTPS externo não atestado | DNS da API aprovado, certificado TLS válido, rota 443, firewall/NSG, SSH 22 restrito /32, nenhuma porta PG exposta e validação de ingress/egress. |
| IAM e segredos | Nenhum Vault/chave operacional aprovado neste pacote | Políticas de mínimo privilégio, credenciais por serviço, rotação/revogação, chave protegida fora do checkout, APK, env de outro processo e logs. |
| PostgreSQL staging | SQL M40923–M40929 foi testado em PG18 efêmero, não em staging real | Banco separado do Termux original `:5433`, contas técnicas independentes, ACL/owners/GUC/SECURITY DEFINER/RLS, backups cifrados e restauração ensaiada, monitoração e rollback. |
| Backend | FastAPI original/commit/PID/processos não reatestados | Proveniência de imagem/binário, processo e DSNs, segregação guardian/emissor/app, CI, autenticação e observabilidade; 503 em gravações Master até aprovação independente. |
| Android | APK debug não é release | Teste físico de topo/teclado/logout, biometria e perfis, certificado release, testes de rede, política de atualização. |

Templates disponíveis para revisão (não executar): `infra/oci/staging-reuse/Caddyfile.template`, `fr-finance-staging-api.service.template`, `staging-runtime.env.example`. Não usar `terraform apply`, `oci compute instance launch`, `systemctl start` ou configurar webhook público com base neste documento.

## Mercado Pago Connect: sequência proposta

1. **Aprovação de modelo comercial**: confirmar formalmente, com Mercado Pago e jurídico, quem recebe, mantém e movimenta fundos, a modalidade de cobrança, capacidades Pix e eventual split/saída. A plataforma FR Finance não se declara banco, mas isso não elimina exigências regulatórias do fluxo real.
2. **Aplicação e consentimento do vendedor**: registrar `redirect_uri` HTTPS **estático e aprovado**; usar `state` imprevisível e de uso único, associado a usuário/tenant/sessão e TTL; aplicar PKCE quando suportado/configurado; verificar consentimento e destinatário antes da troca de código. Nunca logar `code`, `code_verifier`, `access_token` ou `refresh_token`.
3. **Credenciais e rotação**: permitir apenas worker independente obter/trocar/renovar token em armazenamento cifrado por vendedor/tenant; impedir que o Master acesse recursos financeiros de membros; excluir acesso delegado após revogação/saída.
4. **Webhook**: definir endpoint HTTPS de staging, autenticar `x-signature` conforme a família de produto contratada (incluindo `x-request-id` e `data.id` quando previstos), impor limites, verificar seller/tenant e persistir inbox idempotente com quarentena. Nenhuma assinatura ou POST isolado comprova liquidação.
5. **Leitura autenticada e reconciliação**: buscar recurso no endpoint do produto com credencial autorizada, conferir account/seller, valor, moeda, external reference, status, taxas, estornos, eventos duplicados/fora de ordem e conciliação de **três fontes** (provedor, sistema, razão) antes de alterar status. Sem baixa por CSV manual, callback ou print.
6. **Ensaio controlado**: contas e dados de teste autorizados; testar expiração, refresh, tenant trocado, revogação, assinatura adulterada, replay, retry, timeout e chargeback. Teste sintético não equivale à certificação do provedor. Não processar Pix real nem habilitar saque/transferência.

## Evidências por gate

Cada aprovação deve apontar: identificador do gate/AT, versão Git/commit, ambiente independente, responsável, data, requisito, comando/teste, evidência original redigida sem segredos, resultado, revisão externa, risco residual e decisão explícita. Sem comprovante, usar `PENDENTE`, nunca `PASS`. A matriz histórica continha 20 gates reais, 7 de provedores e 50 AT, sem aprovação independente neste checkpoint.

Referências oficiais consultadas em 20/11/2026:
- [Mercado Pago — OAuth, criação de token e autorização](https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation)
- [Mercado Pago — boas práticas OAuth, state e redirect](https://www.mercadopago.com.br/developers/pt/docs/security/oauth/best-practices)
- [Mercado Pago — Webhooks de Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications)
- [Mercado Pago — contas de teste](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/resources/test-accounts)
- [Mercado Pago — OAuth API/token](https://www.mercadopago.com.br/developers/pt/reference/authentication/oauth/_oauth_token/post)

**Gates inalterados**: `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `M40840=BLOCKED`, `M40930_MASTER_WRITES=BLOCKED`, `PRODUCTION=NO-GO`. Nenhuma secret, conta Mercado Pago, hostname, callback, VM, migração, banco original, webhook ou pagamento foi alterado por este pacote.
