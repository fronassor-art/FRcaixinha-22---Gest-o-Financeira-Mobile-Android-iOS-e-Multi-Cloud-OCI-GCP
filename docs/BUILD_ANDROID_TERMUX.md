# Guia Oficial de Compilação do APK Debug no Termux (Capacitor)
**Projeto:** FRcaixinha 2.2 — Gestão Financeira de Caixinhas  
**App ID:** `com.frcaixinha.app`  
**Conformidade:** Contrato Técnico Mestre (Cláusulas 11.1, 14.1 e 16.2)  
**Data:** Novembro de 2026  

---

## 1. Visão Geral e Princípios de Segurança

O FRcaixinha 2.2 utiliza **Capacitor 8.6+** para empacotar os artefatos compilados pelo Vite (`dist/`) dentro do projeto nativo Android (`android/`).

### Garantias de Segurança Imutáveis:
1. **Sem senhas ou credenciais no pacote:** Não há qualquer chave secreta, senha de banco de dados ou credencial de teste gravada no código-fonte ou nos artefatos.
2. **Sem URL de backend embutida / Portão de Autenticação Ativo:** A variável `VITE_API_URL` não vem pré-definida. Ao abrir o aplicativo compilado, o portão de autenticação institucional permanece **estritamente bloqueado**, informando que a API mobile não está configurada e impedindo conexões com hosts arbitrários.
3. **Sem mock ou login de demonstração:** Não existem credenciais padrão ("admin/admin"), usuários falsos ou atalhos para contornar a autenticação.
4. **Isolamento de configuração local:** O arquivo `android/local.properties` (que aponta para o diretório do Android SDK no celular) pertence exclusivamente ao ambiente local do aparelho. Ele está no `.gitignore` e **nunca** deve ser versionado ou incluído em arquivos ZIP.

---

## 2. Diferença Crítica entre os Arquivos ZIP

Antes de iniciar no Termux, identifique corretamente qual arquivo você baixou:

| Arquivo | Conteúdo | Finalidade | Pode compilar APK? |
| :--- | :--- | :--- | :---: |
| **`FRcaixinha_2.2_Projeto_Completo.zip`** *(~3 MB)* | Código-fonte integral: `package.json`, `package-lock.json`, `src/`, `capacitor.config.ts`, `android/` com `gradlew` e `app/build.gradle`, `backend/` e `docs/`. | **Compilação do APK Nativo Android no Termux** ou desenvolvimento completo. | **SIM** |
| **`dist.zip`** *(~1.3 MB)* | Apenas os arquivos HTML/JS/CSS pré-compilados do frontend web. | Teste rápido em navegador via servidor local (ex.: Python `http.server`). | **NÃO** |

> **ATENÇÃO:** O arquivo `dist.zip` isolado **não é suficiente** para compilar o APK, pois não contém o projeto Android, o Gradle nem as dependências do Capacitor. Use sempre o **`FRcaixinha_2.2_Projeto_Completo.zip`**.

---

## 3. Passo a Passo Técnico no Termux

### Passo 1: Permissão de Armazenamento e Pacotes Base
Conceda permissão de acesso ao armazenamento do celular:
```bash
termux-setup-storage
```
*Toque em **Permitir** na tela do Android.*

Instale os pacotes essenciais do Termux:
```bash
pkg update -y && pkg upgrade -y
pkg install -y nodejs-lts openjdk-17 unzip curl
```

Valide as versões instaladas:
```bash
node -v          # Deve ser v20+ ou v22+
npm -v           # Deve ser v10+
java -version    # Deve confirmar OpenJDK 17
```

---

### Passo 2: Localizar e Validar o Android SDK Existente no Termux
Não presuma um caminho fixo. Localize onde seu Android SDK já está instalado no Termux executando:

```bash
# 1. Verifica se já está nas variáveis de ambiente:
if [ -n "$ANDROID_HOME" ] && [ -d "$ANDROID_HOME/platforms" ]; then
  MY_SDK="$ANDROID_HOME"
elif [ -n "$ANDROID_SDK_ROOT" ] && [ -d "$ANDROID_SDK_ROOT/platforms" ]; then
  MY_SDK="$ANDROID_SDK_ROOT"
# 2. Testa os caminhos mais comuns no Termux:
elif [ -d "$HOME/android-sdk/platforms" ]; then
  MY_SDK="$HOME/android-sdk"
elif [ -d "$PREFIX/share/android-sdk/platforms" ]; then
  MY_SDK="$PREFIX/share/android-sdk"
elif [ -d "/data/data/com.termux/files/home/android-sdk/platforms" ]; then
  MY_SDK="/data/data/com.termux/files/home/android-sdk"
else
  MY_SDK=""
fi

# 3. Valida a existência do SDK:
if [ -z "$MY_SDK" ]; then
  echo "❌ ERRO: Android SDK não localizado no Termux!"
  echo "Certifique-se de que o Android SDK (com platforms e build-tools) está instalado."
  echo "Exemplo de export manual: export ANDROID_HOME=/caminho/do/seu/sdk"
else
  echo "✅ Android SDK validado com sucesso em: $MY_SDK"
  export ANDROID_HOME="$MY_SDK"
fi
```

---

### Passo 3: Conferir o Conteúdo do ZIP antes da Extração
Não utilize curingas para extrair arquivos indiscriminadamente. Confirme que o arquivo baixado em `~/storage/downloads` é o projeto completo:

```bash
# Define o caminho do arquivo baixado
ZIP_FILE="$HOME/storage/downloads/FRcaixinha_2.2_Projeto_Completo.zip"

if [ ! -f "$ZIP_FILE" ]; then
  echo "❌ Arquivo $ZIP_FILE não encontrado em Downloads."
  echo "Baixe o 'Projeto Completo ZIP' pelo AI Studio ou pela Central de Download do app."
  exit 1
fi

# Confere a presença dos arquivos vitais no ZIP:
echo "Verificando estrutura do ZIP..."
unzip -l "$ZIP_FILE" | grep -E "(package-lock\.json|capacitor\.config\.ts|android/gradlew|app/build\.gradle|backend/migrations)"
```
*A saída deve listar todos esses arquivos fundamentais.*

---

### Passo 4: Extrair em um Diretório Novo e Limpo
Extraia o projeto em uma pasta dedicada sem sobrescrever versões anteriores:

```bash
# Cria pasta nova com timestamp para isolamento
WORK_DIR="$HOME/frcaixinha-build-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Extrai o arquivo oficial completo
unzip -q "$ZIP_FILE"

echo "Projeto extraído em: $(pwd)"
```

---

### Passo 5: Instalação Limpa com `npm ci`
O arquivo `package-lock.json` deste projeto foi regenerado e validado deterministicamente no AI Studio (o conflito prévio entre `vite@8` e `esbuild` foi corrigido com `esbuild: ^0.28.0`).

Execute a instalação estrita e limpa:
```bash
npm ci
```
*(Não é necessário usar `--legacy-peer-deps` ou `--force`).*

---

### Passo 6: Compilação Web e Sincronização Capacitor
Execute a compilação do Vite e a cópia de ativos para a pasta Android com o script oficial:
```bash
npm run cap:build
```
*Este comando roda internamente `npm run build && cap sync android`:*
- O Vite compila a aplicação em `dist/`.
- O Capacitor sincroniza `dist/` com `android/app/src/main/assets/public/` e atualiza as configurações.

---

### Passo 7: Configurar e Validar `android/local.properties`
Entre na pasta `android/` e gere o `local.properties` com o caminho validado no Passo 2:

```bash
cd android

# Grava o caminho validado no local.properties
echo "sdk.dir=$ANDROID_HOME" > local.properties

# Validação estrita antes de chamar o Gradle
if [ ! -f "local.properties" ]; then
  echo "❌ ERRO: android/local.properties não existe!"
  exit 1
fi

SDK_CONF=$(grep "sdk.dir" local.properties | cut -d'=' -f2)
if [ ! -d "$SDK_CONF/platforms" ]; then
  echo "❌ ERRO: O caminho '$SDK_CONF' informado em local.properties não contém a pasta 'platforms'!"
  exit 1
fi
if [ ! -d "$SDK_CONF/build-tools" ]; then
  echo "❌ ERRO: O caminho '$SDK_CONF' informado em local.properties não contém a pasta 'build-tools'!"
  exit 1
fi

echo "✅ local.properties configurado e validado: sdk.dir=$SDK_CONF (platforms e build-tools presentes)"
```

---

### Passo 8: Compilar o APK Debug com Gradle Wrapper
Garanta a permissão de execução do Gradle Wrapper e inicie a compilação:

```bash
chmod +x gradlew
./gradlew assembleDebug
```
*O Gradle compilará o código nativo Java/Kotlin e empacotará o APK debug.*

---

## 4. Localização do APK Gerado e Instalação

Após a conclusão bem-sucedida do comando `./gradlew assembleDebug`, o arquivo APK estará localizado em:
```text
android/app/build/outputs/apk/debug/app-debug.apk
```

### Copiar para a Pasta Downloads do Celular:
```bash
cp app/build/outputs/apk/debug/app-debug.apk ~/storage/downloads/FRcaixinha-2.2-debug.apk
echo "✅ APK copiado com sucesso para: /sdcard/Download/FRcaixinha-2.2-debug.apk"
```

### Instalação no Aparelho:
1. Abra o aplicativo **Arquivos** (ou Gerenciador de Downloads) do seu celular.
2. Localize o arquivo `FRcaixinha-2.2-debug.apk`.
3. Toque para instalar.
4. Abra o aplicativo **FRcaixinha 2.2**.

---

## 5. Comportamento Esperado na Primeira Execução

Ao abrir o APK compilado no celular:
1. **Portão de Autenticação Ativo:** O aplicativo abrirá imediatamente na tela institucional de login.
2. **Status Mobile Seguro:** Como `VITE_API_URL` não foi configurada na compilação, o aplicativo exibirá o aviso institucional de que a API remota não foi apontada.
3. **Isolamento de Dados:** Nenhuma tela interna (Cotas, Empréstimos, Livro-Razão) será liberada sem uma sessão JWT real emitida por um backend autenticado.

---

## 6. Tabela de Estado Real das Validações

| Componente / Etapa | Ambiente Testado | Status | Justificativa Técnica Real |
| :--- | :--- | :--- | :--- |
| **`package-lock.json` e `npm ci`** | Sandbox AI Studio | **PASS** | Lockfile regenerado com resolução de `esbuild: ^0.28.0`. `npm ci` executou com sucesso (308 pacotes em 21s). |
| **Scripts `build`, `cap:sync` e `cap:build`** | Sandbox AI Studio | **PASS** | Executados e validados no container: `cap:build` concluiu compilação Vite (963ms) e sync Capacitor (115ms). |
| **Estrutura do ZIP Completo** | Sandbox AI Studio | **PASS** | `FRcaixinha_2.2_Projeto_Completo.zip` possui 153 arquivos incluindo `android/gradlew`, `app/build.gradle` e `package-lock.json`. Sem `local.properties`. |
| **Compilação do APK (`./gradlew assembleDebug`)** | Termux no Celular | **DELEGADO AO CLIENTE** | Não executado no AI Studio; deve ser executado no Termux do usuário que possui o Android SDK. |
| **Políticas RLS PostgreSQL (`SECURITY DEFINER` + `FORCE RLS`)** | Sandbox AI Studio | **BLOCKED** | O contêiner web não possui servidor PostgreSQL ativo. Não é possível afirmar validação em banco real neste ambiente. |
| **Login Real e Sessão FastAPI** | Sandbox AI Studio | **BLOCKED** | Sem banco de dados ativo. O frontend permanece estritamente bloqueado (sem mock/demo). |
