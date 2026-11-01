# FRcaixinha 2.2 — Android debug + FastAPI no mesmo celular

**Escopo:** homologação local no Termux. Não é implantação de produção e não habilita pagamentos reais.

O APK debug do CI recebe apenas `VITE_API_URL=http://127.0.0.1:8000`, sem senha ou token. O Capacitor usa `http://localhost` nesta variante; o Android permite HTTP exclusivamente para `127.0.0.1` e `localhost`, somente em debug. Builds normais preservam HTTPS. A API FastAPI escuta somente `127.0.0.1:8000`. Não exponha o servidor via Wi-Fi, túnel ou `0.0.0.0`.

## Sincronizar sem perder arquivos locais

```bash
cd ~/frcaixinha-aistudio-mobile || exit 1
git status --short --branch
git fetch origin
git merge --ff-only origin/atualizacao-ai-studio-9b46a63187
```

Se houver conflito, não use reset/clean. Interrompa e relate a saída.

## Verificar dependências Python sem instalar ou alterar o banco

```bash
cd ~/frcaixinha-aistudio-mobile
python3 -m uvicorn --version
python3 -c 'import fastapi, asyncpg, psycopg; print("Dependências API presentes")'
```

Confirme o Python ativo no Termux/Debian PRoot. Se faltar pacote, preparar ambiente virtual isolado antes de instalar.

## Iniciar o FastAPI (etapa SEM credenciais)

Em uma sessão do Termux:

```bash
cd ~/frcaixinha-aistudio-mobile
bash backend/scripts/run_termux_fastapi.sh
```

Em outra sessão:

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1:8000/api/health/ready
```

`/api/health` deve retornar 200. Sem PostgreSQL, `/api/health/ready` deve retornar **503**, conforme o bloqueio contratual. Após conectar os papéis separados, `READY_FOR_TEST_AUTH` significa conexão/esquema disponíveis — não comprova que logins de membros funcionam.

## Etapa posterior: contas sintéticas, sob autorização

1. Auditoria **somente leitura** do PostgreSQL local: migrações 001–010, roles separadas, RLS, usuários e backups.
2. Migrações reais apenas após autorização específica.
3. Usar exclusivamente contas **sintéticas** de teste, senhas fortes inseridas em prompt local sem eco.
4. Variáveis do servidor em `~/.config/frcaixinha-2.2/api.env`, com `chmod 600`, sem link simbólico e fora do Git. Nomes: `ENVIRONMENT=homologation`, `FRCAIXINHA_TEST_AUTH=1`, `DATABASE_URL` (financeiro), `AUTH_DATABASE_URL` (autenticação).
5. Validar Master, administrador, membro, admin-membro, troca de contexto e acesso cruzado negado.

**Não envie senhas, tokens, CPFs, URLs PostgreSQL com senha para ChatGPT ou GitHub.** Pix, créditos, pagamentos, rifas e bolões operacionais permanecem bloqueados. O CI não substitui teste WebView ↔ Termux no próprio celular.
