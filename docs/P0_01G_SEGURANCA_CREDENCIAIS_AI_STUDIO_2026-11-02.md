# AI Studio — pacote P0-01g: segurança de sessão e credenciais

Data: 02/11/2026, America/Belem. Desenvolvimento **exclusivo** na PR #2 Draft, branch \`atualizacao-ai-studio-9b46a63187\`.
Baseline da rodada: \`9c0cecea9731269a4518fd1c49996c622ef14bb0\`.

## Escopo do pacote (sem implantação local)

1. Migração 026: fingerprint SHA-256 do hash Argon2id/bcrypt armazenado junto da prova de login.
2. Prova de login de uso único vinculada à versão **efetiva** da credencial. Fingerprints inválidos, provas antigas e credenciais inexistentes são negados.
3. Bloqueio de leitura de credencial com \`FOR SHARE\` antes do bloqueio de prova \`FOR UPDATE\`, em ordem estável entre emissão e rotação.
4. Trigger de rotação de \`password_hash\`: invalida provas pendentes e revoga sessões da identidade inteira, independentemente de tenant.
5. Trigger de exclusão de credencial: invalida provas pendentes e sessões.
6. FastAPI calcula fingerprint apenas da representação armazenada já validada; não armazena senha bruta, hash de senha nem fingerprint em resposta ao cliente.
7. Verificações de conexão rejeitam usuário de banco explicitamente privilegiado no DSN (camada adicional de segurança, não substitui inspeção efetiva de roles).
8. Prontidão FastAPI exige SQL role não privilegiada, sem leitura de hashes para Auth, sem INSERT direto de sessão, com funções mínimas de Auth e leitura restrita do verificador.
9. Testes de CI PostgreSQL 16 e 18 verificam provas sintéticas, replay, expiração, divergência de usuário, rotação e concorrência entre duas conexões.
10. Script do Termux tem a migração 026 listada apenas para FUTURO procedimento autorizado.
11. Guardas de pós-migração auditam as duas triggers.
12. Documentação conserva explícita a distinção entre homologação, testes CI descartáveis e produção.

## Fronteiras de ameaça e riscos remanescentes

**Reduzidos:** reuso de prova, alteração de credencial enquanto uma prova ainda é válida, autenticação de conta com credencial excluída, revogação incompleta por contexto, emissões simultâneas usando a mesma prova.

**Não resolvidos:** comprometimento total do backend, verificador e Auth sob controle conjunto do invasor, limite de tentativas em memória por processo, transporte/TLS e armazenamento de segredos, recuperação de conta, registro de identidade por e-mail, auditoria de logs e segurança de dispositivos. Uma credencial verificadora isoladamente ainda pode criar provas para qualquer identidade cuja senha tenha hash acessível; ela não consegue emitir sessão sem a credencial Auth. Conta owner PostgreSQL permanece altamente privilegiada: nunca deve constar dos DSNs da API.

## Gates para aceitar a rodada

- CI frontend e TypeScript: PASS.
- CI API sem banco: PASS.
- CI PostgreSQL 16 (usuários e dados sintéticos): PASS.
- CI PostgreSQL 18 (migrações 001–026 em transação única e RLS): PASS.
- CI APK debug: PASS.
- CI concorrência: exatamente um vencedor, em duas conexões Auth reais.
- Confirmação: PR continua Draft; \`main\` sem merge; sem uso de Termux para desenvolvimento; nenhum segredo ou pagamento real.

## Regras operacionais

Nenhuma migração local, conta verificadora local, rotação real de credenciais, bootstrap Master, instalação APK ou transferência financeira está autorizada. O banco \`frcaixinha_aistudio_dev\` no PostgreSQL 18.6, porta 5433, deve permanecer com **0 tabelas** até decisão explícita. Nenhum percentual da matriz de 147 cláusulas pode ser declarado concluído sem auditoria requisito a requisito.

**Próxima etapa após CI:** revisão independente do fluxo de troca/redefinição de senha, provisionamento de usuário verificador com segredo independente em cofre, rate limit compartilhado e inspeção detalhada de todas as rotas de autenticação; não proclamar produção pronta.
