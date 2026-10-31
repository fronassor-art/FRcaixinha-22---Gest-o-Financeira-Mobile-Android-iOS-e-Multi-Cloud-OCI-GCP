# FRcaixinha 2.2 — Gestão Financeira Mobile (Android & iOS) e Multi-Cloud (OCI + GCP)

Sistema financeiro completo para caixinhas de empréstimos (Tabela Price), cotas, rifas com rateio proporcional, bolões oficiais (Quina de São João, Lotofácil da Independência, Mega da Virada) e arquitetura em nuvem híbrida com custódia e auditoria imutável (Oracle Cloud Infrastructure WORM SHA-256 + Google Cloud Platform).

---

## 📱 Execução no Celular via Termux (Android)

Você pode rodar o **FRcaixinha 2.2** 100% nativo dentro do seu celular Android utilizando o **Termux**, sem precisar de computador.

### Passo 1: Instale os pacotes necessários no Termux
Abra o Termux e digite:
```bash
pkg update -y && pkg install -y nodejs git unzip curl
```

### Passo 2: Dê permissão de acesso aos arquivos
```bash
termux-setup-storage
```
*(Toque em "Permitir" na janela que abrir no Android)*

### Passo 3: Baixe e extraia o projeto
Se você baixou o arquivo `FRcaixinha_2.2_Projeto_Completo.zip` pelo navegador do celular:
```bash
mkdir -p ~/frcaixinha && cd ~/frcaixinha
cp ~/storage/downloads/FRcaixinha_2.2_Projeto_Completo.zip .
unzip -o FRcaixinha_2.2_Projeto_Completo.zip
```

### Passo 4: Como Rodar no Celular (2 Métodos)

#### Método A (Recomendado — Sem Node.js, Sem Erros de C++):
Como o projeto já inclui a pasta `dist/` pré-compilada, você pode usar o servidor embutido do Python que não requer compilação:
```bash
pkg install -y python
cd ~/frcaixinha/dist
python -m http.server 3000
```

#### Método B (Com Node.js):
```bash
cd ~/frcaixinha
npm install
npm run dev
```

> **Apareceu o erro "CANNOT LINK EXECUTABLE node"?**
> Esse erro ocorre quando a biblioteca `libc++` do Termux está desatualizada. Para corrigir:
> ```bash
> pkg update -y && pkg upgrade -y
> pkg install -y libc++ nodejs-lts
> ```
> *(Dica: Se o seu Termux veio da Google Play Store, ele foi descontinuado em 2020. Instale a versão moderna pelo F-Droid ou GitHub).*

### Passo 5: Abra no celular
Abra o **Google Chrome** no seu celular e acesse:
```
http://localhost:3000
```
O aplicativo abrirá instantaneamente em alta performance, funcionando mesmo sem internet (offline).

---

## 💻 Execução no Computador (Windows / macOS / Linux)

### Pré-requisitos
- **Node.js LTS (v18+)**
- **Git**

### Comandos
```bash
npm install
npm run dev
```
Acesse `http://localhost:3000`.

---

## 🚀 Publicar no seu GitHub a partir do Termux ou PC

```bash
git remote add origin https://github.com/SEU_USUARIO/frcaixinha-22.git
git branch -M main
git push -u origin main
```

---

## 🛡️ Cláusulas e Regras de Negócio Implementadas
- **Empréstimo Tabela Price:** 5 parcelas de R$ 167,19 com taxa de juros 20% a.m. decrescente sobre saldo devedor, juros totais R$ 335,96, sem taxas administrativas.
- **Módulo de Rifas:** 3 campanhas anuais (Março, Junho, Setembro - dia 20), R$ 50,00 por cota (10 bilhetes de R$ 5,00), premiação configurável.
- **Bolões Oficiais:** Quina de São João, Lotofácil da Independência e Mega da Virada com margem de 20% para a caixinha e rateio estrito de prêmios.
- **Multi-Cloud Híbrido:** Failover automático GCP <-> OCI e logs de auditoria imutável (WORM).
