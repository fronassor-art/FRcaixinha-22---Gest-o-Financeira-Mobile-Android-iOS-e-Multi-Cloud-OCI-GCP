# AI Studio M3101–M3200 — Política OCI de recuperação e continuidade

Este pacote transforma em testes de código os controles dos itens 13.1–13.6 (com 9.9) do Contrato Técnico Mestre disponível entre as referências históricas do aplicativo. O arquivo histórico está rotulado FRcaixinha 2.2; **não alterar o ambiente independente anterior**.

## Verificador criado

`backend/app/oci_recovery_policy.py` valida metadados de evidência trazidos por auditoria autorizada: região de homologação, servidor/deploy, banco privado, HTTPS, IAM mínimo, isolamento Vault, cópia externa, backup cifrado, arquivamento WAL, retenção, ensaio de restauração, metas de RPO/RTO, alerta, revisão de custo e reconciliação pós-restauração.

### Gates contratuais representados

- Backup completo **criptografado diariamente**: última evidência até 24 horas.
- WAL arquivado a cada **até 15 minutos** (quando suportado pela infraestrutura): exige que o servidor prove suporte/ativação. Se não suportado, bloqueia prontidão operacional, sem inventar alternativa.
- Retenção **mínima de 35 dias**, com cópia externa segregada do servidor principal.
- Restauração testada **antes de produção** e depois **trimestralmente** (janela de verificação 90 dias para preflight conservador).
- RPO de até **60 minutos**, RTO de até **480 minutos**, observados e registrados em teste real.
- Não autorizar Pix real sem conformidade e aprovação da infraestrutura e do Mercado Pago para cada finalidade; saúde do aplicativo deve continuar sem efeitos financeiros.

**Um resultado `eligible_for_manual_review=true` é somente pré-revisão de metadados fornecidos; NÃO prova que as evidências são autênticas, e NÃO autoriza `terraform apply` ou dinheiro real.** O código não chama Oracle Cloud, não lê CPF, não envia backups e não faz migrações. O check `EXTERNAL_ATTESTATION` requer referência, mas precisa ser validado por humanos, IAM e registros de terceiros.

## Considerações OCI

Segundo a documentação oficial de OCI Database with PostgreSQL, há políticas de backups diários, semanais e mensais com retenção automática de até 35 dias; isso **não comprova** suporte aos WAL, RPO/RTO ou restauração da instalação escolhida. É necessário escolher o serviço/arquitetura real e demonstrar tudo antes do go-live.

Fonte OCI: https://docs.oracle.com/en-us/iaas/Content/postgresql/backups.htm

### Pendências

OCI ainda não provisionada. Para cada meta registrar data, console/job, região, segurança, hash e teste real. A Issue #3 permanece aberta. Nenhuma configuração de nuvem ou banco foi modificada.
