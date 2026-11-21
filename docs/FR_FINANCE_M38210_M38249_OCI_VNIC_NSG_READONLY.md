# FR Finance AI Studio — M38210–M38249: inspeção autenticada da VNIC/NSG OCI (somente leitura)

Origem: M38209, commit ab17da9, 1.600 testes Python PASS no Termux. Branch AI Studio exclusiva.

## Lacuna real
O inventário anterior M37470 observa VCN, subnet, Security Lists e alguns requisitos de IAM, mas **não** identifica a VNIC primária da VM indicada nem avalia as regras ingress de seus NSGs. Esse é um bloqueio de segurança relevante antes de uma API HTTPS pública.

## O que foi entregue
- M38210–M38219: política sem IO em `backend/app/oci_vnic_perimeter_readonly.py`. Verifica snapshot com região sa-saopaulo-1, compartimento do staging, nome de subnet/VCN, máquina e VNIC primária, IP público IPv4 e regras ingress por NSG.
- M38220–M38229: observação de candidato de entrada IPv4 443 aberto no NSG; sinalização de SSH público 22 e PostgreSQL público 5432/5433, inclusive quando a fonte for um IP externo individual. Regras amplas TCP ou ALL são revisadas como exposição, sem pressupor proteção do firewall do host.
- M38230–M38239: `backend/scripts/aistudio_oci_vnic_nsg_readonly.py` exige autorização explícita para consulta real. Usa OCI SDK configurado no Termux/PRoot com chamadas GET/LIST apenas; confere o compartimento ativo fr-finance-staging, a instância exata informada no intake público, o vínculo da VNIC principal, a subnet e a VCN FR Finance, e os NSGs anexados. Nunca imprime IDs, IP, nomes de política, respostas OCI ou erros SDK.
- M38240–M38249: testes adversariais offline, fixture de múltiplos NSGs, intervalos e protocolos, listas inconsistentes, IPs privados/metadata, estados de VM, sinalizações de 443/22/5432/5433 e verificação estática das operações permitidas. CI sem credenciais OCI, sem rede, sem banco.

## Comandos seguros no Termux
Modo offline (sem rede):
```sh
python backend/scripts/aistudio_oci_vnic_nsg_readonly.py offline
```

Somente depois de confirmar que OCI_REGION, OCI_COMPARTMENT_OCID e OCI_INSTANCE_OCID no intake do operador apontam para recursos reais, executar **explicitamente** leitura remota:
```sh
python backend/scripts/aistudio_oci_vnic_nsg_readonly.py live AUTHORIZE_OCI_VNIC_READ_ONLY
```
Se o OCI_INSTANCE_OCID ainda não existir, a leitura real retornará BLOQUEADO com motivo fixo. A rotina não cria nem procura uma máquina, não interfere com o observador A1 já ativo e não solicita upgrade pago.

## Limites do diagnóstico
Uma VNIC/NSG com 443 exposto é somente **candidata de regra**, não prova reachability ou HTTPS. Security Lists, NSG efetivo na VNIC, roteamento, firewall do sistema operacional, proxy, certificado TLS, API, banco/RLS, IAM, backup/restauração e segregação de tenants requerem auditorias independentes. Uma VNIC sem IP público pode ser arquitetura válida com proxy/load balancer, que ainda precisa ser comprovada. Este novo relatório nunca autoriza deploy ou ativação.

Nenhuma migration foi criada. Banco original PostgreSQL 5433, dados locais e produção preservados; CLOUD_MUTATIONS=NONE; EMAIL_REAL=OFF; PIX_REAL=OFF; ATIVACAO_REAL=OFF; PRODUCAO=BLOCKED.
