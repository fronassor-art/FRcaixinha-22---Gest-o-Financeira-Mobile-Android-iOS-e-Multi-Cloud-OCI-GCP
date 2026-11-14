# FR Finance AI Studio — M37318–M37322 | OCI readiness real, sem provisionamento

**Base comprovada:** M37311 `065e44faadc19fc2f0741cf8290f64d19b33c390`,
GitHub 6/6 PASS, 74 testes Termux; inventário OCI SDK READ_ONLY_PASS.
**Sinal subsequente real, M37317 (09/11/2026):** consulta SDK da rede
retornou READ_ONLY_PASS com a rede existente:
- `sa-saopaulo-1` — VCN/subnet `FR Finance` disponíveis, CIDR privado;
- subnet permite IP público na VNIC, IGW habilitado e default route até IGW;
- apenas 1 security list associada à subnet;
- regras públicas TCP 80, 443, 22, 5432, 5433 **não presentes** na
  security list; NSGs, firewall host, DNS e HTTPS não auditados;
- inventário anterior, no momento da consulta: **0 VMs RUNNING na raiz,
  0 RUNNING ou PROVISIONING no staging e 0 Vaults ACTIVE no staging**.

**Limitação temporal:** são duas consultas distintas, não um snapshot
atômico. Não inferir recurso inexistente para sempre, nem concluir
ausência de VMs desligadas, outros compartimentos ou NSGs.

## Correção prática M37318 — formato real OCI SDK

A função `oci.util.to_dict` produz atributos Python como
`display_name`, `cidr_blocks`, `security_list_ids`,
`destination_port_range`, `network_entity_id`. O parser anterior
esperava chaves da OCI CLI como `display-name`, `cidr-blocks`, etc.;
se tentasse uma auditoria real, falharia mesmo com recursos válidos.

`backend/scripts/aistudio_oci_existing_network_readonly.py` passa a
normalizar as chaves recursivamente para o formato esperado,
rejeitando colisões e tipos desconhecidos. Os fixtures CI foram
alterados para fornecer **o formato real do Python SDK**, não
respostas artificiais pré-normalizadas. Testes também cobrem
vulnerabilidades de schema e bloqueio de comandos inesperados.

## M37319–M37322 — gates operacionais únicos de staging

`backend/app/oci_staging_operational_readiness.py` reúne,
**somente para fins de diagnóstico**, as observações dos módulos
`oci_staging_live_inventory` e `oci_existing_network_audit`.
`backend/scripts/aistudio_oci_operational_gates_readonly.py` faz
ambas as consultas autenticadas na OCI e imprime somente estados,
contagens e códigos de pendência, sem OCIDs, IPs, CIDRs, PEM, token,
segredo ou erro bruto do provedor. Usa o Python da venv OCI no Debian.
Uma consulta inválida bloqueia e não aprova a implantação.

Quando a conta ainda reportar 0 VMs e 0 Vaults com a porta pública 443
sem regra na security list, os blockers mínimos serão:
`OCI_STAGING_RUNNING_VM_ABSENT`,
`OCI_STAGING_ACTIVE_VAULT_ABSENT`,
`OCI_HTTPS_443_INGRESS_NOT_PREPARED`,
além de provas ainda inexistentes de IAM, NSG, SO, DNS/TLS,
PostgreSQL TLS/RLS, backup/restore, backend autenticado, Mercado Pago
e autorização financeira. Quando uma VM aparecer, **a contagem só
remove o primeiro blocker**; nunca autoriza ativação automática.

## Sequência futura de implantação — não executar agora

| Fase | Pré-requisito independente | Mutação permitida agora |
| --- | --- | --- |
| 1 | OCI Always Free A1/E2 host capacity real e decisão de custo | NÃO |
| 2 | VM `RUNNING` no compartimento correto, VNIC validada | NÃO |
| 3 | Instance Principal, Dynamic Group e IAM mínimo | NÃO |
| 4 | Vault `DEFAULT` standard/software protegido; confirmar preço e limite | NÃO |
| 5 | Backend FastAPI isolado + proxy reverso HTTPS 443, DNS e firewall/NSG | NÃO |
| 6 | PostgreSQL staging remoto segregado, TLS verify-full, roles/RLS | NÃO |
| 7 | Backup cifrado, restore testado, logging, health, rollback | NÃO |
| 8 | E-mail Brevo SPF/DKIM/DMARC, MP OAuth/webhook homologados | NÃO |
| 9 | Testes funcionais de administrador/membro e revisão de licenças | NÃO |
| 10 | Pix e ativações reais: autorização humana separada | NÃO |

A infraestrutura de rede permite planejar **reuso da VCN/subnet**
sem criar outra VCN. Isso **não comprova** VM, HTTPS ou segurança NSG
e não autoriza alterar portas. Manter 5432/5433 privados. A regra
pública 443 só será planejada com TLS, firewall, WAF/rate-limit e
arquitetura segura. Não abrir 22 indiscriminadamente: preferir
acesso administrativo por mecanismo restrito como OCI Bastion
quando disponível e autorizado.

**Não executar** o Terraform `infra/oci/staging/network.tf`
sem revisão explícita: ele criaria rede nova, em vez de reutilizar
a `FR Finance` existente.

**Catálogo:** 106 SQL, sem migração nova.
**PostgreSQL Termux 5433:** não modificado.
**Mercado Pago, Pix e usuários reais:** DESATIVADOS.
**Gastos, VM, Vault, DNS/rotas/security lists:** NÃO ALTERADOS.

## Uso posterior, após aprovação de CI + sincronização Termux

```bash
proot-distro login debian --bind "$HOME/fr-finance:/mnt/fr-finance" -- bash -lc '
  export PATH=/root/.venvs/oci-cli/bin:$PATH
  export PYTHONDONTWRITEBYTECODE=1
  /root/.venvs/oci-cli/bin/python3 /mnt/fr-finance/backend/scripts/aistudio_oci_operational_gates_readonly.py
'
```

O resultado `OCI_M37322_STATUS=READ_ONLY_PASS` **não é**
`DEPLOYMENT_AUTHORIZED`. As pendências continuarão explícitas.

## Nota de integridade CI

Runs anteriores do M37316 (`42671682836`, `42672618328` e
`42673424186`) não apresentaram o conjunto completo de seis jobs.
Testes do módulo OCI passaram em PostgreSQL 18, mas isso não
equivale a 6/6 PASS. Não divulgar homologação total antes de haver
seis jobs registrados e concluídos com sucesso.
