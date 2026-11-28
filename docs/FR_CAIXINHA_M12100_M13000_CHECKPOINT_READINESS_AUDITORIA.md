# FR Caixinha AI Studio — M12100–M13000: checkpoint offline e matriz P0 de persistência

## Referência
- Checkpoint local confirmado: \`dabdf97\`, FastAPI PID \`20704\`, PostgreSQL \`127.0.0.1:5433\`, contratos M7900–M12000 PASS.
- Projeto exclusivo **AI Studio** — não misturar FRcaixinha-2.2.
- Sem uso de dinheiro real, sem aplicação de migrações locais ou OCI.

## Limites de interpretação

**Checkpoint de retomada:** um \`OfflineCheckpoint\` é calculado a partir de todos os snapshots que o chamador apresenta. Um adversário que omita eventos e substitua o manifesto pode criar um conjunto internamente coerente. **Não é prova de durabilidade, origem bancária, assinatura, armazenamento ou recuperação comprovada após queda real.**

**Checklist de persistência:** \`StagingReadinessClaims\` contém apenas declarações com tipo estrito. Mesmo declarando os 24 requisitos como true, a API não autentica as evidências; \`apply_migration_authorized\`, \`oci_deploy_authorized\`, \`real_payment_authorized\` e \`ledger_write_authorized\` seguem false.

## Entregas efetivas de software — 48 controles verificados em código

### M12100–M12300: protocolo offline
1. Criação de manifesto com identidade de tenant.
2. Vínculo do seller.
3. Vínculo da operação.
4. Vínculo do Order ID alegado.
5. Vínculo do Payment ID alegado.
6. Contagem de snapshots de entrada.
7. Contagem de observações únicas.
8. Contagem de replay exato.
9. SHA-256 de ponta da cadeia M12000.
10. Contador de tentativas final.
11. Horário final normalizado UTC.
12. Domínio versionado e JSON canônico.

### M12400–M12600: retomada com política restritiva
13. Rejeição de manifesto adulterado.
14. Rejeição de prefixo retirado.
15. Rejeição de prefixo substituído.
16. Rejeição de mudança de caixinha.
17. Rejeição de mudança de operação.
18. Rejeição de mudança de Order.
19. Rejeição de mudança de Payment.
20. Rejeição de retrocesso temporal.
21. Rejeição de salto de tentativas.
22. Rejeição de edição dos eventos anteriores.
23. Suporte a replays idênticos, sem side effects.
24. Retorno explícito sem permissão de GET, ledger ou payout.

### M12700–M12900: requisitos P0 de staging para futura prova externa
25. Exigir RLS habilitada.
26. Exigir FORCE RLS.
27. Exigir sessão autenticada ligada ao tenant.
28. Exigir menor privilégio e sem BYPASSRLS na aplicação.
29. Exigir audit log append-only com sequência única.
30. Exigir identidade auditada de operadores e 2 revisores distintos.
31. Exigir unicidade global de operação, Order e Payment.
32. Exigir isolamento transacional e teste de concorrência real.
33. Exigir lease durável para recuperação.
34. Exigir testes de crash/restart em banco externo.
35. Exigir autenticação independente de extrato bancário.
36. Exigir vínculo de seller ao provedor.
37. Exigir proteção de segredos por Vault.
38. Exigir assinatura de webhook.
39. Exigir âncora externa assinada do checkpoint.
40. Exigir recuperação de backup com RLS preservada.
41. Exigir TLS e rotação de credenciais.
42. Exigir revogação de operador testada.

### M13000: regressão e governança
43. Recusar declarações booleanas ambíguas e tenants nulos.
44. Recusar compartilhamento de seller entre caixinhas.
45. Recusar duplicação de tenant na mesma matriz.
46. Contadores resumidos sem identificar seller.
47. CI inclui teste independente \`test_m13000_checkpoint_readiness_ci.py\`.
48. Health route somente diagnóstica \`/api/health/features/m13000\`, com flags de autorização falsas.

## Pendências P0 e ordem de execução recomendada

1. Elaborar e revisar migração física de tabelas de incidentes/auditoria **sem aplicá-la ainda**, validar DDL e RLS em ambiente temporário isolado.
2. Conectar identidade real de operador/revisor às permissões RLS por sessão de banco, respeitar Administrador Master exclusivo.
3. Implantar índices globais/idempotência e prova de concorrência com duas transações; lease durável e restauração de checkpoint auditável.
4. Auditoria append-only e prova externa com assinatura/âncora independente; backup/restore, ataque de rollback e detecção de evento omitido.
5. Integrar PSP e banco com credenciais de tenant isoladas, autenticação de origem e conciliação independente; antes de qualquer ativação financeira, homologar backend/API/Android e governança.
6. Testes AT-01–AT-50 no aparelho, perfis Administrador, Master e Membro, incluindo Livro-Razão, extrato e paginação.

**Neste pacote: nenhuma migração, nenhum SQL aplicado, nenhum worker ligado, nenhum OCI apply, nenhuma operação real, nenhuma liberação de hold ou merge.**