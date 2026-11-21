# FR Finance AI Studio — M29500–M29800

Este pacote atua exclusivamente no repositório AI Studio. A sincronização com
o celular é feita **dentro de `$HOME/fr-finance` no Termux
normal**. Nunca rodar comandos do projeto no Debian `root@localhost` da
automação OCI.

## Entregas
- **M29500:** correlação de fechamento de exatamente duas caixinhas com anos
  coincidentes; bloqueio de eventos financeiros cruzados e de IDs reutilizados.
- **M29600:** detecção de 90 dias de atraso e de três competências consecutivas
  como fatos diferentes; tratamento distinto entre caixinha do proprietário
  e outras; saída voluntária pendente mantém direitos e reservas.
- **M29700:** composição com `simulate_contract_closing` existente, percentual
  fixo 15% administrador / 85% membros, sem incluir principal de cota no lucro,
  precisão integral de centavos e reserva de valores não distribuíveis.
- **M29800:** testes adversariais, CLI somente leitura e CI integrada.

O oráculo calcula prévias sintéticas: não conecta à OCI, ao PostgreSQL real,
ao Mercado Pago nem a e-mail. Não altera credenciais, auditorias, RLS ou
migrações. Uma CI verde não substitui conciliação, comprovação jurídica ou
autorização de fechamento real.

## Termux — executar após CI aprovada
```bash
cd "$HOME/fr-finance"
git remote -v
git branch --show-current
git status --short
git fetch origin atualizacao-ai-studio-9b46a63187
git merge --ff-only origin/atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m29500_m29800_two_tenant_closing_ci.py
PYTHONPATH=backend python3 backend/scripts/aistudio_m29500_m29800_checkpoint.py audit
```

**ATENÇÃO:** não aplicar SQL à porta 5433 neste pacote. Migrações devem
ser planejadas e autorizadas à parte após auditoria do banco local.
