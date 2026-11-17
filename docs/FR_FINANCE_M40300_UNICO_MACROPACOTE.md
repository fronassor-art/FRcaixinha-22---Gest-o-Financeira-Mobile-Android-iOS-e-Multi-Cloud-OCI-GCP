# FR Finance M40300 - Macropacote unico, quatro frentes, sem VM

Projeto exclusivo FR Finance; branch atualizacao-ai-studio-9b46a63187; PR #2 Draft. Marco anterior: CP20261117, commit 77203fc, matriz ampliada de 330 verificacoes. A VM OCI ainda nao existe segundo o operador; a CI nao se conecta a OCI.

**Invariantes:** um repositorio original GitHub, um diretorio nativo Termux $HOME/fr-finance e um cluster PostgreSQL FR Finance original em 127.0.0.1:5433/frcaixinha_aistudio_dev. FR Caixinha 2.2 totalmente separado. Sem sistemas duplicados, novas pastas de trabalho, banco de teste permanente ou novo app.

## Reuso de algoritmos existentes

1. Seguranca: M40220 (12 acessos anonimos HTTP401 no dispositivo), M40230 (dois tenants/tres perfis sinteticos), M40070 (PG18 descartavel e autenticacao).
2. Credito: M39010/M39020/M39033/M39082, router especial atual, schema de campanha, preferencia opt-in/out e outbox bloqueado.
3. Financeiro: Price original, closing_contract_oracle, member_cycle_rules, two_tenant_closing_ci; sem duplicar motores ou modificar politicas comerciais.
4. Android: sessionResumeGuard, authService, specialCreditRequestBoundary e SpecialCreditView. Preserva o package debug .aistudio e assinatura release separada.

## Mudancas implementadas e provas

| Frente | Codigo alterado | Evidencia |
|---|---|---|
| Seguranca e isolamento | Associar destinatario-grant-membro-tenant-ciclo no SQL de oportunidade, resposta e publicacao. Permitir apenas rotas/métodos especificos de credito por perfil no cliente. | Testes negativos de tenant B, admin, membro revogado e path traversal sem novas sessoes. |
| Credito Especial | Regressões do ciclo fechado/futuro, membro revogado, resposta unica, interesse/recusa, opt-in sem entrega e consentimento de canal. Nenhum envio. | TestClient sintético em rotas existentes, outbox sem dispatcher e nenhum loan criado. |
| Financeiro | Rejeitar movimento de capital cujo dia local fica fora do ciclo; reforcar testes de conservacao de centavos Price (96 cenarios), reordenacao, repeticao, duplicata, capital nao e lucro e dois tenants. | Oraculos originais e pytest sem SQL real; nenhum desembolso. |
| Android e documentos | Bloqueio de paths fora da API, excecao de rede sem retry de POST, tela libera busy por epoch apos troca de perfil, testes foreground, versoes de contrato e divergenicas SQL. | Node/TS e build web; prova fisica do APK ainda nao realizada. |

## Diagnostico Termux apos CI

O script backend/scripts/frfinance_m40300_termux_readonly.sh deve ser usado somente apos git fast-forward seguro na pasta original. Observa apenas pg_ctl status no PGDATA original, pg_isready 127.0.0.1:5433 e GET /api/health 127.0.0.1:8000. Nenhum psql, DDL, DML, restart, create, token ou senha. Se ambos OFF, a conclusao e SERVICOS_DESLIGADOS_OU_NAO_VISIVEIS, nunca PERDA DE BANCO. Reinicio de processos exige identificacao separada e autorizacao; nao e realizado pelo pacote.

M40240 (auditoria do catalogo live PG18) ainda NAO EXECUTADO: comandos anteriores pararam no Git por SHA incorreto/fetch divergente. A ultima sincronizacao comprovada no Android foi M40230 28b16e9. Nao reaplicar migracoes SQL110/111/112/113. M40300 nao tem migracoes SQL.

**Aceites:** codigo, testes sinteticos, typecheck e build web sao comprovacoes do escopo de engenharia. RLS autenticado original, envio FCM, provedores financeiros, assinatura release, APK no aparelho, VM, HTTPS, Vault e producao continuam dependentes de evidencias posteriores. Nenhum teste offline pode assinar automaticamente 0/20 gates tecnicos, 0/7 gates externos ou 0/50 cenarios de aceite.

PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
