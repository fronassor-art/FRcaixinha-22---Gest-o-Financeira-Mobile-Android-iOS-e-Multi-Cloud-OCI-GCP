# FR Finance — M37361–M37370 | Auditoria estrutural PostgreSQL local (somente leitura)

Checkpoint anterior: M37360 Termux 23/23 PASS; 106 SQL versionados; auditoria
OCI autenticada registrou 17 bloqueios, sem VM/Vault no staging, Pix real OFF.
GitHub Actions 6/6 PASS no commit 53321b0.

## Objetivo que pode avançar independentemente da OCI
As marcações M19300, M20100 e M20700 do inventário SQL pedem comprovação
no PostgreSQL local. O catálogo versionado não indica quais migrações
estão aplicadas. A nova rotina M37370 faz apenas SELECT no pg_catalog
do banco local exclusivo frcaixinha_aistudio_dev, porta 5433, PG18.

Audita: identidade do cluster e transação read-only; tabelas lifecycle
028/029 com FORCE RLS e índice 030; oito tabelas sintéticas 034–041
com FORCE RLS e ausência de grants a app/auth; inbox 031 FORCE RLS;
contrato mínimo 043, constraints 150 (NOT VALID), defaults removidos
e grants da função legacy; seis contratos de acesso auth M22600.

* STRUCTURAL_PRESENT: as estruturas consultadas foram observadas.
* NOT_ATTESTED: estrutura ausente, parcialmente divergente ou não atestada.
* BLOCKED: credencial, projeto, identidade ou leitura não conferem.
Nenhum dos três significa que há histórico de execução de cada arquivo
SQL; também não é aprovação de produção ou de Pix.

O script só aceita checkout limpo em ~/fr-finance na branch e HEAD idêntico
ao origin local. Exige o cluster Termux PG18 documentado, a role específica,
transação somente leitura, e solicita a senha por prompt oculto, sem
registrá-la em arquivo, log, comando ou GitHub. **Não enviar a senha ao chat.**
Se o data_directory do cluster não coincidir, termina bloqueado e não
recomenda modificar o cluster por causa da auditoria.

## Execução
Primeiro conferir GitHub Actions 6/6 e sincronizar a branch.
No Termux, executando FORA do Debian PRoot, usar:

PYTHONDONTWRITEBYTECODE=1 python backend/scripts/aistudio_local_pg18_evidence_readonly.py

Se psycopg não estiver instalado no Python Termux, a rotina retorna
BLOCKED; não instalar dependências sem examinar o ambiente.
Divulgar somente a saída sanitizada, nunca senha ou DSN.

## Segurança e limites
Nenhuma migração ou comando DDL, nenhuma tabela de usuários ou
credenciais consultada; apenas catálogos públicos e funções de
verificação de grants. O script não altera PostgreSQL e não acessa OCI.
O sucesso do M37370 não remove os bloqueios M37360 (VM, Vault, rede,
IAM, TLS, RLS staging e recovery), que dependem de evidências separadas.
106 SQL continuam registrados. PIX_REAL, MERCADO_PAGO_REAL e
REAL_USER_ACTIVATION continuam OFF.
