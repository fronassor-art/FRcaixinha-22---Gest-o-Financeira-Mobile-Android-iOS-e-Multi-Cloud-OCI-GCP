# PROMPT OFICIAL — AUDITORIA GOOGLE AI STUDIO (SOMENTE LEITURA)

Você está recebendo o projeto **AI Studio**, exportado do repositório
\`fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP\`.
O projeto é INDEPENDENTE de qualquer outro FRcaixinha, mesmo quando identificadores históricos coincidirem.

## Escopo e restrições
1. Audite exatamente o conteúdo do ZIP anexado; confirme \`COMMIT_ORIGEM.txt\`, quando disponível, e o SHA informado no relatório.
2. Execute auditoria **somente leitura** e relatório de propostas. NÃO modifique o projeto sem autorização posterior.
3. NÃO conecte contas reais, serviços externos, Pix, Mercado Pago, usuários reais, credenciais ou banco local do Termux.
4. A \`main\` deve permanecer intacta; a PR #2 permanece Draft. Nenhuma migração local é permitida.
5. Não considere telas demonstrativas como operações financeiras executáveis ou backend operacional.

## Verificações obrigatórias
- Conferir importação do projeto React/TypeScript/Vite e estrutura Capacitor Android 8.
- Identificar a diferença entre preview Web no AI Studio, APK Android e backend FastAPI.
- Verificar se o APK debug isolado realmente utiliza \`com.frcaixinha.app.aistudio\` sem alterar outro aplicativo.
- Conferir que \`VITE_API_URL=http://127.0.0.1:8000\` é apenas desenvolvimento no mesmo aparelho.
- Analisar tela inicial/login sem servidor, tratamento de falha 503/rede, telas bloqueadas, vazamento de dados e estado offline.
- Auditar identidade única, contextos Master/Admin/Membro e segregação de tenant.
- Conferir migrações 001–027 e CI; verificar rate limit por HMAC, bloqueio 5/60 s, RLS, rotatividade de credenciais e ausência de credenciais reais.
- Revisar acessibilidade, contraste, navegação Android, teclado, rolagem, visual de erros, desempenho e permissões.
- Verificar ausência de saídas financeiras reais; não tocar em pagamentos ou instâncias Cloud.

## Entrega esperada
Forneça uma tabela \`ID | severidade | evidência arquivo:linha | risco | reprodução | correção proposta | teste de regressão\`.
Separe PASS, FAIL e BLOCKED; identifique impedimentos reais do primeiro teste em Android.
Apresente plano P0/P1/P2 com patches **sugeridos** e testes executáveis apenas em CI descartável.
Explique como importar/ver o projeto no AI Studio, mas NÃO realize publicação ou sincronização automática.
