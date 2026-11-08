# FR Finance AI Studio — M28500: homologação externa de e-mail (checkpoint manual)

Data da evidência: **08/11/2026**, horário de Belém. Frente exclusiva **FR Finance AI Studio**, sem misturar com FRcaixinha 2.2. Branch `atualizacao-ai-studio-9b46a63187`; PR #2 mantida em **DRAFT**, sem merge.

## Escopo e origem da evidência

Este documento registra informações comprovadas pelo operador com capturas de tela do **Registro.br**, **ImprovMX**, **Brevo** e do **Gmail**, além de uma saída de execução isolada do Python no Termux. É uma **homologação operacional manual**, não um teste executado pela CI, não é uma atestação de infraestrutura OCI e não é autorização de produção.

**Não registrar** tokens, login SMTP completo, chave SMTP, senha, códigos de SMS, códigos de backup, e-mail pessoal de destino, IP residencial ou conteúdo de `provider-public-inputs.json`.

## Evidências observadas

| Verificação manual | Resultado observado | Limitação |
| --- | --- | --- |
| Registro.br — domínio `frfinance.com.br` | Registrado; zona DNS avançada editável | Não comprova disponibilidade do app |
| ImprovMX — MX 10 `mx1.improvmx.com` e MX 20 `mx2.improvmx.com` | Ambos reconhecidos | São DNS/recebimento, não envio |
| ImprovMX — TXT SPF da raiz | Reconhecido: `v=spf1 include:spf.improvmx.com ~all` | Não alterar indiscriminadamente |
| Encaminhamento `contato@frfinance.com.br` | Mensagem de teste recebida no Gmail do operador | Outros aliases ainda sem teste individual |
| Aliases `suporte@frfinance.com.br` e `notificacoes@frfinance.com.br` | Criados no ImprovMX | Recebimento individual ainda não testado |
| Brevo — TXT `brevo-code`, DKIM 1, DKIM 2, DMARC | Quatro verificações ficaram verdes | Não implica envio automático pelo backend |
| Brevo — domínio `frfinance.com.br` | Painel exibiu **Autenticado** | Subdomínio de marca não configurado, opcional |
| Brevo — remetente `notificacoes@frfinance.com.br` | **Verificado**, DKIM e DMARC verdes | Não prova worker/outbox |
| Brevo — chave SMTP de teste | Criada e guardada fora do GitHub/chat | **Não** guardar valor no repositório |
| Termux Python SMTP isolado | `FR_FINANCE_SMTP_ACCEPTED=PASS` via `smtp-relay.brevo.com:587` com STARTTLS | Prova de aceite em teste manual, não liberação do backend |
| Gmail destino | Mensagem `FR Finance - Teste SMTP` recebida em 08/11/2026, 04:03 (Belém) | Prova manual de entrega para um destinatário |

## Estado de segurança obrigatório

- `FR_FINANCE_REAL_MAIL=OFF`: integração automática ao backend **não habilitada**.
- `FR_FINANCE_REAL_USER_ACTIVATION=OFF`.
- `FR_FINANCE_PIX_INBOUND=OFF` e `FR_FINANCE_PIX_OUTBOUND=OFF`.
- Cadastro do operador no Termux: **8/13 campos públicos**; faltam `OCI_INSTANCE_OCID`, `OCI_DATABASE_HOST`, `OCI_VAULT_OCID`, `MP_OAUTH_REDIRECT_URI`, `MP_WEBHOOK_URL`.
- Segredos de SMTP, MP, autenticação e banco só podem ser configurados em serviço de segredos apropriado com política de mínimo privilégio e versões, após controle de custo e implantação. A credencial de teste **não** foi inserida em variável de ambiente persistente ou código pelo procedimento de prova manual.
- Não habilitar envio automático nem usuários reais somente porque o teste isolado recebeu `PASS`.

## Pendências e critérios de liberação

1. **OCI**: região principal `sa-saopaulo-1`, compartment de staging existente. A capacidade A1/E2 Micro foi reportada **OUT_OF_HOST_CAPACITY** pelo operador; nenhuma VM criada. Reavaliar disponibilidade/quotas e preço real sem contratar ou provisionar silenciosamente.
2. **SMTP em staging**: provisionar Vault com orçamento aceito, IAM mínimo, rotação da chave de teste para credencial operativa, worker de outbox com deduplicação/idempotência, fila de falha/quarentena, limites e trilha de auditoria.
3. **Segurança**: não divulgar credenciais, não colocá-las no APK, Git, capturas ou logs; manter 2FA da Brevo ativo e códigos de recuperação em cofre privado.
4. **E-mail**: validar assinatura DKIM/SPF/DMARC da mensagem em cabeçalhos, testes de bounce/erro e consentimento próprio quando aplicável. Remover o alias curinga `*` apenas após análise dos casos reais de uso.
5. **Mercado Pago**: callback OAuth exato e webhook somente quando um HTTPS real estiver disponível; Pix real e saída Money Out permanecem bloqueados até os critérios próprios.
6. **Banco**: preservar `frcaixinha_aistudio_dev`, PostgreSQL 18 na porta `5433`; não aplicar migrations de CI/staging no banco local.

## Verificação segura no Termux (sem chaves, sem rede dos provedores)

```bash
cd "$HOME/frcaixinha-aistudio-mobile"
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py audit
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py next
PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py secrets-plan
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git status --short
```

As saídas acima atestam apenas as propriedades que medem. `GATE_MAIL_PROVIDER=PROVIDER_ATTESTATION_REQUIRED` pode persistir mesmo com prova externa manual, pois o contrato exige verificações e isolamento operacional em staging.

**Checkpoint M28500:** documentação do teste real externo, **sem novo código de envio, sem alterar banco, sem ativar Pix ou e-mail do aplicativo**.
