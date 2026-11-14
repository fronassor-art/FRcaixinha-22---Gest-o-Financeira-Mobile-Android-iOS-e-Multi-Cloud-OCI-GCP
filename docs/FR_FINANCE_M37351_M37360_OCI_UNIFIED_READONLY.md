# FR Finance — M37351–M37360: unified OCI READ ONLY

Base: M37350, commit 52f60fb, 58 testes IAM PASS, catalogo 106 SQL.
Regiao: sa-saopaulo-1. PostgreSQL local 5433 nao alterado.

O pacote consolida inventario OCI (VM e Vault), rede existente e
grupos/politicas IAM numa unica auditoria com validacoes de contexto.
A leitura retorna contagens e nomes fixos de bloqueios, nao imprime
OCIDs, politicas integrais, tokens, perfis OCI ou valores de segredos.

O resultado M37360_STATUS=READ_ONLY_PASS atesta somente que as
consultas read-only completaram e foram validadas. Nao e liberacao para
hospedar, criar recursos, ativar usuarios ou operar Pix real.
A classificacao IAM M37350 foi ampliada: a leitura deve ser repetida;
contagens antigas de candidatos nao sao prova de ausencia de acesso.

Arquivos:
- backend/app/oci_unified_readiness_readonly.py
- backend/scripts/aistudio_oci_unified_readonly.py
- backend/tests/test_m37351_m37360_oci_unified_readonly_ci.py

Comando Termux local, apos sincronizacao da branch:
PYTHONPATH=backend python -m pytest -q backend/tests/test_m37351_m37360_oci_unified_readonly_ci.py

Para revalidacao OCI autenticada somente leitura, no Termux:
proot-distro login debian --bind "$HOME/fr-finance:/mnt/fr-finance" -- bash -c '
set -eu
export PATH="/root/.venvs/oci-cli/bin:$PATH"
export PYTHONDONTWRITEBYTECODE=1
/root/.venvs/oci-cli/bin/python3 /mnt/fr-finance/backend/scripts/aistudio_oci_unified_readonly.py
'

Nao copiar arquivos OCI de configuracao, PEM, OCIDs, matching rules,
declaracoes IAM, tokens ou secret values ao chat. Compartilhar apenas
saida sanitizada do programa.

Permanecem OFF: Mercado Pago real, Pix real e ativacao de usuarios.
Nenhuma migracao local, instancia, Vault, politica, rede ou firewall
e criada ou alterada pelo pacote. Provisionamento pago exige aprovacao
explicita e verificacao de custos antes de qualquer mudanca.
