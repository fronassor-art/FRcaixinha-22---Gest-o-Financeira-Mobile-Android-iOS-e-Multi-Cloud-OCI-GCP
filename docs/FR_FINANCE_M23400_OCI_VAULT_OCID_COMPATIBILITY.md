# M23400 — OCID oficial do OCI Vault e custo de segredos efêmeros

A Oracle documenta o identificador de um segredo como `ocid1.vaultsecret.<realm>.<region>.<id>`. Os padrões anteriores `ocid1.secret` eram fictícios e impediriam chamadas reais ao OCI Secrets. Este pacote ajusta validadores de leitura e de staging, SQL 034/035/045, fixtures descartáveis, testes de regressão e os respectivos hashes do catálogo de migrações.

Documentação Oracle: https://docs.oracle.com/en-us/iaas/Content/secret-management/Tasks/view-secret-details.htm

**Risco de custo e ciclo de vida:** a exclusão de segredos OCI é agendada, não instantânea (por padrão 30 dias; intervalo configurável descrito no guia oficial). Criar um novo segredo do Vault para *cada* tentativa OAuth/PKCE pode multiplicar recursos e custo. O estado OAuth no PostgreSQL já tem consumo único e TTL; antes de produção, comparar custo e segurança de PKCE efêmero criptografado com OCI KMS, ou solução igualmente segura, em vez de alegar que a exclusão agendada equivale a revogação física imediata.

Documentação Oracle: https://docs.oracle.com/en-us/iaas/Content/secret-management/Tasks/delete-secret.htm

**Estado operacional:** nenhuma instância OCI foi provisionada, nenhum segredo foi escrito, nem houve deploy, migração local ou chamada ao Mercado Pago neste pacote. O adaptador OAuth continua desativado. Webhook e Pix reais OFF. Substituição das referências fictícias na infraestrutura OCI requer testes de integração e orçamento explícito antes da ativação.
