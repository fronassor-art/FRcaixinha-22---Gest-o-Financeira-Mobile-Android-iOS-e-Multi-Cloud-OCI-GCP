# Aplicativo AI Studio — FastAPI e APK debug no mesmo celular

**Este documento pertence EXCLUSIVAMENTE ao repositório**
`fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`,
branch `atualizacao-ai-studio-9b46a63187`. O repositório
`fronassor-art/FRcaixinha-2.2` é OUTRO projeto. Não compartilhar bancos, clusters, usuários, credenciais, backups ou arquivos de configuração.

## Estado e bloqueios

- APK debug: `VITE_API_URL=http://127.0.0.1:8000` para falar com o FastAPI no mesmo telefone. O Android permite HTTP loopback somente em debug.
- O PostgreSQL usado anteriormente no Termux em `$PREFIX/var/lib/frcaixinha_2_2_pg18` (porta 5432) **não deve ser usado** pelo AI Studio. Ele foi iniciado antes desta correção; não aplicar migrações nem fazer login com credenciais do outro aplicativo.
- O banco próprio deste projeto AI Studio **ainda não foi confirmado/criado no Termux**. A existência de SQL e testes no GitHub Actions NÃO demonstra que o banco exista no celular.
- Convenção reservada para isolamento futuro (não significa recursos já criados): cluster `$PREFIX/var/lib/frcaixinha_aistudio_pg18`, TCP `127.0.0.1:5433`, banco `frcaixinha_aistudio_dev`, papéis `frc_ai_app` (financeiro) e `frc_ai_auth` (autenticação). Os dois papéis acessam o **mesmo banco separado**, como no CI; isso não permite usar o banco do projeto antigo.
- Arquivo privado de ambiente exclusivamente `~/.config/frcaixinha-aistudio-mobile/api.env` no ambiente em que o servidor for executado; `chmod 600`, sem links simbólicos, fora do repositório.
- O script `backend/scripts/run_termux_fastapi.sh` rejeita `DATABASE_URL` ou `AUTH_DATABASE_URL` que não apontem exatamente à porta/banco/papel AI Studio previstos. Não criar esses recursos automaticamente.
- Nunca colocar senhas, tokens ou URLs de conexão com segredo no GitHub, ChatGPT ou APK. Sem transações, créditos, Pix, rifas ou bolões reais.

## Verificação sem mudança de banco

```bash
cd ~/frcaixinha-aistudio-mobile || exit 1
git remote -v
git status --short --branch
echo "=== CLUSTER ANTIGO, STATUS APENAS ==="
pg_ctl -D "$PREFIX/var/lib/frcaixinha_2_2_pg18" status || true
echo "=== CLUSTER EXCLUSIVO AI STUDIO, EXISTENCIA APENAS ==="
if [ -f "$PREFIX/var/lib/frcaixinha_aistudio_pg18/PG_VERSION" ]; then
  echo "AI_STUDIO_CLUSTER=EXISTE"
else
  echo "AI_STUDIO_CLUSTER=NAO_CRIADO_OU_NAO_ENCONTRADO"
fi
```

Não rodar `initdb`, `createdb`, `psql` com usuário legado, `pg_ctl start`, `pg_restore` ou migrações com base em suposições. Primeiro auditar permissões, caminhos, portas e esquema da exportação; pedir autorização específica antes de criar cluster/banco ou migrar.

## Python Debian PRoot

O Python nativo do Termux pode não ter FastAPI. Usar um ambiente virtual Python **exclusivo para esta exportação AI Studio**, por exemplo `/root/.venvs/frcaixinha-aistudio` dentro do Debian PRoot. O manifesto está em `backend/requirements.txt`. A instalação de dependências não configura PostgreSQL.

Com as dependências disponíveis, pode-se iniciar o FastAPI **sem banco**. O script permite `DATABASE_URL` e `AUTH_DATABASE_URL` vazios simultaneamente; nesse modo `/api/health` deve responder 200 e `/api/health/ready` deve responder 503.

```bash
# Dentro do Debian PRoot, usando o clone AI Studio visível no ambiente:
cd /data/data/com.termux/files/home/frcaixinha-aistudio-mobile
PYTHON_BIN=/root/.venvs/frcaixinha-aistudio/bin/python bash backend/scripts/run_termux_fastapi.sh
```

Em outra sessão do Termux, confirmar `curl -i http://127.0.0.1:8000/api/health` e `curl -i http://127.0.0.1:8000/api/health/ready`.

## Cadastro de contas de homologação (futuro)

Somente depois de confirmar o cluster exclusivo e validar o SQL do projeto AI Studio, criar com autorização explícita contas sintéticas Master, administrador e membro e testar identidade única/múltiplos papéis e RLS. Nunca usar usuários `frc22_owner`, banco `frcaixinha_2_2_dev` ou arquivos do projeto independente. A autenticação existente continua limitada à homologação.
