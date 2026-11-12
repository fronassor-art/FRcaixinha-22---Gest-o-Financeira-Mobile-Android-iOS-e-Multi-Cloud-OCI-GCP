# Contrato Técnico Mestre — FR Finance AI Studio

**Escopo exclusivo:** engenharia e fronteiras de segurança do FR Finance AI Studio, produto independente do projeto FR Caixinha 2.2. Este documento define uma **especificação técnica versionada**, não substitui contratos de adesão assinados nem valida o conteúdo jurídico das 147 cláusulas históricas.

## A. Repositório, diretório e rastreabilidade
- Repositório de desenvolvimento: `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP` (slug histórico preservado).
- Branch: `atualizacao-ai-studio-9b46a63187`; PR #2 rascunho. Alterações de software são validadas por CI e sincronizadas localmente com fast-forward.
- Pasta canônica no Termux Android: **`$HOME/fr-finance`**; migração a partir do nome anterior feita **uma única vez** com `backend/scripts/frfinance_rename_termux_directory.sh`. Não clonar de novo.
- Ambiente OCI de automação no Debian PRoot: separado do repositório Android; nunca executar sincronização ou migração do projeto em `root@localhost`.

## B. Aplicação e contratos de interface
- Frontend React + TypeScript + Capacitor; UI, `metadata.json`, pacote npm e título FastAPI devem se identificar como **FR Finance**.
- Android `appId=com.frcaixinha.app`, namespace, esquema de deeplink, assinatura e versionCode preservados **por compatibilidade de atualização**, sem transformar o nome legado em marca pública.
- API FastAPI com `/api/v1`; autenticação por credenciais segregadas, sessões com expiração/revogação e contexto explícito por papel. `MASTER`, `TENANT_ADMIN` e `TENANT_MEMBER` não permitem escalada de privilégio entre caixinhas.
- PostgreSQL RLS com validação de tenant na consulta e na escrita. Credencial verificadora de senha não emite sessão e credencial de sessão não lê hashes de senha.
- Logs, resposta HTTP e documentos novos devem omitir senhas, tokens, hash de credenciais, dados pessoais e URLs privadas.

## C. Dados e política de migração
- Banco **exclusivo do AI Studio** em Termux: PostgreSQL 18, porta `5433`, banco `frcaixinha_aistudio_dev`. Não modificar nome/porta ou importar dados do FR Caixinha 2.2.
- Catálogo histórico verificado no M29800: **92 arquivos SQL versionados**, com subclasses local, CI e staging. A existência de SQL em Git não prova migração aplicada ao banco local.
- Nenhuma sincronização Git autoriza `migration apply`. Antes de migração, conferir Git SHA/branch, lista e hash dos SQL, roles, versão de schema, backup restaurável, impacto transacional e autorização separada. Nunca aplicar arquivos CI/staging ao PostgreSQL local `5433`.
- Manter testes de concorrência, idempotência, reversão, segregação de caixa Master e caixas de administradores e recuperação de incidentes.

## D. Motor financeiro
- Entradas da plataforma (assinaturas) e de cada caixinha (contribuições/retornos) são independentes.
- Livro-Razão, capital e rateio não confiam em confirmação isolada de webhook nem em operações do dispositivo: exigir observação financeira autorizada, consulta ao provedor, conciliação e lançamentos auditáveis.
- Rateio anual: administrador da caixinha 15% do lucro líquido real elegível; membros elegíveis 85% por Capital-Dias, com Decimal e conservação exata de centavos. Capital principal excluído do lucro.
- Regras de atraso, três competências não quitadas, 90 dias, contratos de saída e restituição requerem evidência e controle jurídico; jamais operação monetária por mera prévia calculada.

## E. Identidade e fluxo de contratação
- Master convida administrador sob MFA e aprovação independente; administrador só convida membros do próprio tenant.
- Convite com uso único, prazo, revogação e chave por tenant, registro transacional e outbox durável; prova real de titularidade do e-mail deve vir de provedor homologado.
- Aceite afirmativo vinculado a versão publicada do texto integral canônico e identidade real; operação concorrente deve ser atômica. Recuperação de senha revoga sessões anteriores.
- Rotas públicas de convite e recuperação ficam bloqueadas até testes end-to-end reais de staging e aprovação formal.

## F. Infraestrutura, distribuição, provedores
- OCI São Paulo e Android release exigem HTTPS, DNS, firewall, TLS válido, roles, paridade de migração, restauração de backup em ambiente isolado, assinatura APK persistente e teste de atualização física.
- Mercado Pago Connect exige OAuth multiempresa, PKCE/estado, rotação e cifragem de credenciais; Pix de entrada exige Orders, notificações verificadas, idempotência e reconciliação; Pix de saída depende de autorização comercial Money Out.
- Produção não é liberada por CI verde, VM criada ou campo de configuração preenchido. A matriz [M28700–M29000](FR_FINANCE_SUPER_MACRO_M28700_M29000_RELEASE_EVIDENCE.md) registra **20 provas técnicas** e **7 gates externos** pendentes de homologação operacional.

## G. Exclusividade dos documentos
- Documento de produto vigente: [Caderno Mestre FR Finance](CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md).
- Histórico técnico: [registro original de 147 cláusulas](FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json).
- Os arquivos originais FRcaixinha 2.2 em `public/assets/aistudio/` ficam intactos como **fontes históricas**, sem adotar seus títulos como documentos vigentes nem alterar seus SHA-256.
- Alterações contratuais requerem avaliação específica; esta edição de identidade **não** transfere autorização financeira, legal ou de ativação.

**Estado de execução:** `PRODUCTION_NOT_AUTHORIZED` · `REAL_USERS=OFF` · `REAL_PIX=OFF` · `LOCAL_MIGRATIONS_APPLIED=NO`.

## H. Crédito Especial/Extraordinário — CTM-CRED-EX-01 a CTM-CRED-EX-06 (desenvolvimento autorizado; operação real bloqueada)
- **Origem histórica:** cláusula 4.2 do Documento Mestre 14/09/2026, consolidação 6.2 de 26/09/2026 e cláusula 12 da minuta de adesão 12/10/2026. Trata-se de recuperar os princípios da exceção contratual para a frente **FR Finance AI Studio**, sem transplantar bancos/contratos do FRcaixinha 2.2.
- **CTM-CRED-EX-01:** somente TENANT_ADMIN titular poderá registrar autorizações excepcionais por membro ativo da própria caixinha, ciclo, limite positivo em BRL, justificativa de risco e validade. Autorização de solicitação ≠ aprovação/garantia/contrato/reserva/desembolso. Limites extraordinários por membro; a avaliação financeira, garantia quando exigida, liquidez, concentração e contratos permanecem obrigatórios.
- **CTM-CRED-EX-02:** campanhas com destinatários individuais ou selecionados em lote, rascunho, publicação na caixa interna, resposta INTERESTED/DECLINED, revogação e expiração; não criar empréstimos automaticamente.
- **CTM-CRED-EX-03:** entrega prioritária **push Android**, com e-mail Brevo, WhatsApp Cloud e SMS Brevo concebidos no mesmo macropacote, mas **sem ativação por associação**: cada canal tem preferências, credenciais, permissões e homologação próprias.
- **CTM-CRED-EX-04:** consentimento granular para marketing, opt-out independente e tratamento LGPD; mensagem de tela bloqueada sem dados financeiros. Ausência de preferência equivale a não autorização do canal.
- **CTM-CRED-EX-05:** rastreabilidade, RLS FORCE, separação rigorosa por tenant/membro, idempotência, sanidade de valores e expiração. Master não gerencia nem visualiza empréstimos de outras caixinhas. Nenhuma rota do pacote libera Pix, altera ledger ou movimenta dinheiro.
- **CTM-CRED-EX-06:** executar somente em sandbox com dados fictícios até aprovação de migração local, homologação de Android/FCM e aprovação jurídica-operacional de provedores e crédito real. CI e-mails/FCM/WhatsApp/SMS devem indicar NÃO HOMOLOGADO até envio autorizado verificável.
- **Contrato detalhado e matriz operacional:** [FR_FINANCE_CREDITO_ESPECIAL_EXTRAORDINARIO_M39010.md](FR_FINANCE_CREDITO_ESPECIAL_EXTRAORDINARIO_M39010.md). Esta aprovação autoriza desenvolvimento de código e documentação, **não** migração Termux, comunicação externa ou operações financeiras reais.
