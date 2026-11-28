# FR Finance AI Studio — Supermacropacote M29900–M30300

**Registro executivo em 09/11/2026:** a avaliação histórica de 01/11
contém 147 requisitos: 58 parciais, 50 bloqueados, 34 não verificados,
5 divergentes. **84 pendências de prioridade** são BLOQUEADO ou NÃO
VERIFICADO. Essa classificação é um retrato de 01/11, NÃO uma contagem
revalidada da situação técnica atual.

## Entregas executáveis

- **M29900:** módulo `backend/app/contract_clause_coverage.py` lê
  individualmente os 147 IDs do registro M24000 e confere unicidade,
  classificação, trabalho e ações, sem alterar o arquivo-fonte.
- **M30000:** para cada cláusula, acrescenta uma trilha de revisão:
  código candidato, teste candidato, presença de arquivos, trabalho
  responsável, próximos passos e evidência externa necessária.
  **Arquivo presente não equivale a implementação correta nem a cláusula
  comprovada.** A associação é por área funcional, não avaliação de
  correspondência individual assinada.
- **M30100:** 16 frentes de trabalho mapeadas à matriz de 20 gates
  técnicos e 7 verificações externas. Nenhum gate é desbloqueado.
- **M30200:** cobertura CI parametrizada por todas as 147 cláusulas,
  rejeição de entradas manipuladas e de vínculos faltantes, travas da
  produção e verificação de ausência de escrita em banco/OCI.
- **M30300:** registro **AT-01..AT-50**, explicitamente
  **NÃO EXECUTADO**. Seus roteiros de negócio precisam ser comparados
  ao texto contratual autorizado antes de criar cenários específicos;
  não inventamos os títulos dos 50 casos nem declaramos 50 testes E2E.

### O que este pacote pode confirmar

- Todas as 147 cláusulas do registro histórico recebem uma linha
  independente auditável no inventário do código;
- nenhuma das 50 bloqueadas ou 34 não verificadas é omitida;
- arquivos candidatos de engenharia e teste existem quando indicados;
- há uma ação textual e uma prova externa exigida por cláusula.

### O que NÃO está homologado

Nenhuma linha passa automaticamente a CONCLUÍDA. Não há evidência
independente de cada cláusula em PostgreSQL staging e dispositivo real,
aprovação jurídica, autenticação/MFA Master, provedor de e-mail, Pix
Orders/Connect/Money Out ou fechamento com movimentação real. A presença
de fontes, CI ou inventário de ATs não constitui homologação comercial.

### Termux — diretório único correto

Após a CI do commit correspondente ser aprovada:

```bash
cd "$HOME/fr-finance"
git status --short --branch
git fetch origin atualizacao-ai-studio-9b46a63187
git merge --ff-only origin/atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m29900_m30300_contract_coverage_ci.py
PYTHONPATH=backend python3 backend/scripts/aistudio_m29900_m30300_contract_audit.py audit
PYTHONPATH=backend python3 backend/scripts/aistudio_m29900_m30300_contract_audit.py priority
```

Sem migrações, sem segredos, sem acesso OCI. Não é necessário renomear
ou recriar o clone. Os originais FR Caixinha 2.2 são preservados como
fontes históricas, sem confusão com o Caderno e Contrato FR Finance.

### Macropacotes subsequentes

Prioridade de implementação (um requisito pode exigir vários pacotes):
1. Identidade/convite/consentimento e banco transacional real em staging;
2. cobrança SaaS e contas segregadas Master/administradores;
3. Livro-Razão, inadimplência, saída, juros e rateio sob conciliação;
4. provedores OAuth/Orders/SMTP em ambientes de teste autorizados;
5. OCI, backup/restore, proteção web, assinatura Android;
6. evidências E2E, decisões jurídicas e revisão das divergências.

Toda nova rodada deve produzir commit, testes CI e relatório do Termux,
com continuidade a partir do resultado enviado pelo operador.
