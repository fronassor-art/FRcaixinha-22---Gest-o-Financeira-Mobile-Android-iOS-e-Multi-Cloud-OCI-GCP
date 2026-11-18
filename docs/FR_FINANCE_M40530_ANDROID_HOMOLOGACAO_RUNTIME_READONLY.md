# FR Finance M40530 — homologação visual Android e diagnóstico de runtime sem alterações

**Data:** 18/11/2026. **Base física:** APK M40520 debug com identificador visível `7708159` (CI 7/7 PASS). **Destino da branch:** `atualizacao-ai-studio-9b46a63187`, PR #2 Draft. **Decisão financeira:** NO-GO.

## Homologação física — relato e capturas do operador

Seis capturas do APK instalado foram analisadas no chat, **não arquivadas no GitHub** por conterem fotos e dados pessoais. O operador confirmou expressamente **biometria funcional e fotografia de perfil funcional**. Em imagens do aparelho foram observados:
- Build `7708159` e painéis segregados de administrador e membro, nomes coerentes com seus perfis e estado de homologação sem pagamentos.
- Seletor de acesso com logotipo completo em capturas posteriores e após troca/saída de área.
- Entrada no formulário com teclado aberto, campos e botão Entrar acessíveis após rolagem.
- **Ressalva:** em uma das capturas iniciais a parte superior do logotipo estava fora da área visível, enquanto as seguintes mostravam o logotipo integral. A imagem isolada não demonstra se havia scroll manual ou uma persistência indevida. Sem reprodução controlada não declarar defeito definitivamente corrigido em todos os cenários, mas não introduzir novo ajuste visual especulativo.

**Resultado:** `APK_M40520_CONFIRMED`; `BIOMETRICS=PASS_OPERATOR_ATTESTED`; `AVATAR=PASS_OPERATOR_ATTESTED`; `ADMIN_MEMBER_SCREEN=PASS_VISUAL`; `IME_FORM_ACCESSIBLE=PASS_VISUAL`; `LOGO_TOP=PASS_OBSERVED_WITH_SCROLL_CAVEAT`; `PRODUCTION=BLOCKED`.

## Continuidade de engenharia M40530

Foi implementado o diagnóstico `backend/scripts/frfinance_m40530_runtime_readonly.py` com duas modalidades:

- Sem argumentos: **source-only**, sem API, sem PostgreSQL, sem comandos de sistema.
- `--live-readonly`: exclusiva para Termux nativo no checkout original `$HOME/fr-finance`. Revalida a identidade de repositório/branch/PGDATA do FR Finance via M38794/M40150, verifica a existência dos executáveis oficiais `pg_ctl` e `pg_isready`, executa **somente** `pg_ctl status` do PGDATA FR Finance e `pg_isready` **somente** em `127.0.0.1:5433`, sem autenticação SQL, e só depois faz **quatro GET sem acesso ao banco** contra a API em `127.0.0.1:8000` (health, checkpoint, marcador de código e OpenAPI). Reutiliza o classificador e controles do M40190, porém **não chama `/api/health/ready`**, pois essa rota abre conexões PostgreSQL com as URLs carregadas no FastAPI e ainda não há atestado do destino delas. Não consulta deliberadamente a porta 5432 ou a base FR Caixinha 2.2.

O executável inicializa explicitamente a raiz do repositório em `sys.path` antes de importar módulos internos, inclusive com Python isolado. As funções originais usadas já tinham os próprios controles de falha fechada. O diagnóstico novo é apenas um agregador, não altera essas funções nem escreve arquivos. Saídas não exibem credenciais, DSNs, respostas JSON integrais, e-mails ou conteúdo de contas.

**Limitações:** `pg_isready` comprova aceitação de conexão TCP/protocolo, não identidade autenticada do banco; `pg_ctl status` comprova estado relatado do PGDATA, não DDL/RLS; o diagnóstico M40530 **não invoca** `/api/health/ready` e portanto **não valida disponibilidade/autenticação SQL da API**. A inspeção de dados e URLs de banco permanece etapa separada e condicionada a prova segura de destino. Mesmo um resultado `PASS_LOCAL_READONLY_NOT_PRODUCTION` **não atesta PID, bytecode em execução, SHA carregado, paridade SQL110–113, staging OCI, autenticação Master de produção, integrações ou financeiro real**.

### CI offline

- `backend/tests/test_frfinance_m40530_runtime_readonly_ci.py`: onze testes sintéticos de aprovação restrita, identidade de projeto errado, executáveis ausentes, PG desligado/inacessível, API bloqueada, exceções, CLI sem efeitos e ausência de mutações.
- `.github/workflows/frfinance-m40530-runtime-readonly-ci.yml`: CI somente de fonte, sem contato com serviços. Exigir PASS antes de sincronizar. Um teste executa Python isolado em outro diretório para comprovar importação sem `PYTHONPATH`; dois testes adicionais confirmam que apenas as quatro rotas sem banco podem ser consultadas e que falhas de marcador interrompem a verificação. A suíte geral permanece independente.

### Comando autorizado — executar no **Termux, fora do Debian**, após aprovação CI e sync seguro

```bash
(
set -euo pipefail
test "${PREFIX:-}" = "/data/data/com.termux/files/usr"
cd "$HOME/fr-finance"
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187"
python -B backend/scripts/frfinance_m40530_runtime_readonly.py
python -B backend/scripts/frfinance_m40530_runtime_readonly.py --live-readonly
)
```

A segunda chamada verifica serviços já existentes, sem iniciá-los, desligá-los ou reiniciá-los. Se o servidor estiver offline, o diagnóstico retornará **BLOCKED** sem tentar corrigi-lo. Não editar PGDATA, `api.env`, chaves, URLs privadas, usuários ou tabelas. Não executar SQL/migrações ou religar pagamentos em decorrência desse resultado.

**M40530_MIGRATIONS=NONE; M40530_DB_WRITES=NONE; M40530_FASTAPI_RESTART=NONE; M40530_POSTGRESQL_RESTART=NONE; M40530_PIX_REAL=OFF; M40530_PAGAMENTOS_REAIS=OFF; M40530_ATIVACAO_REAL=OFF; M40530_PRODUCTION=BLOCKED.**
