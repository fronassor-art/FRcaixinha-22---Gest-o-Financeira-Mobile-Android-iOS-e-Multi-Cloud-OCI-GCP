# PROMPT OFICIAL — CODEX CLOUD: AUDITORIA APK AI STUDIO (READ ONLY)

Repositório EXCLUSIVO:
\`fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP\`
Branch: \`atualizacao-ai-studio-9b46a63187\`
PR #2: DRAFT; nunca fazer merge para main.
O trabalho é INDEPENDENTE do outro FRcaixinha.

Sua tarefa: AUDITORIA SOMENTE LEITURA do HEAD atual do GitHub.
Não criar commits, alterar arquivos, iniciar migrações locais, provisionar contas humanas, expor segredos, acionar Pix/financeiro, instalar APK ou alterar infraestrutura.

Plano de execução:
1. Registrar HEAD SHA, árvore limpa, nome do repositório e branch. Se divergente, BLOCKED.
2. Analisar diferenças da rodada de empacotamento APK em relação a \`c6012bc4b31d50dd7fb5d01191f44462404c2a6e\`.
3. Revisar Gradle: variante debug tem applicationId único, assinatura debug, networkSecurityConfig restrito a loopback, permissões mínimas e nome visível independente.
4. Analisar se a build do GitHub Actions empacota source no HEAD real da PR e não no merge temporário; validar SHA.
5. Auditar frontend, login e mensagens de erro na ausência do backend 127.0.0.1:8000 e com PostgreSQL local ainda vazio.
6. Auditar migracões 025/026/027, prova vinculada à senha, rejeição de replay, rate limit HMAC e concorrência; considerar falhas sob carga.
7. Verificar controles de isolation multi-tenant, dados sensíveis, logs, cache, WebView, interceptação de tráfego e permissões Android.
8. Revisar se GitHub Actions 5 jobs + job de exportação passam; comparar resultado com o commit sob auditoria.
9. Gerar checklist de testes no smartphone e propostas ordenadas por P0/P1/P2, sem implementar.

Entregue relatório com PASS/FAIL/BLOCKED, evidências \`arquivo:linha\`, comandos não destrutivos, limitações de produção e recomendações de mudanças para aprovação expressa.
