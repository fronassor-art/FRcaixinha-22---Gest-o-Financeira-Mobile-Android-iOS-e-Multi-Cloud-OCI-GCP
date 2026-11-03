# FRcaixinha AI Studio — Ciclo acelerado por macropacotes de 20 itens
Data: 03/11/2026. Projeto AI Studio exclusivo, **não o FRcaixinha 2.2 independente**.
Baseline aprovado e homologado visualmente: `243fe005688d4cf6c75d3d734bcaaeb9a5e34658`, GitHub Actions #195 6/6 PASS.
PR #2 em Draft, nenhum merge na main. Hash do APK anterior: `243fe00`.

## Regra de numeração e entrega
- Macropacotes **120, 140, 160, 180, 200** são MARCOS de 20 verificações
  e não números de execuções do GitHub Actions, que seguem a sequência automática.
- Cada macropacote somente será APROVADO quando CI e testes físicos combinados
  forem verificados; APK debug é candidato até homologação no Android.
- **Não** avançar em migrações no banco local, dinheiro real, contratação real,
  Pix, convite real ou autorização de crédito. Usar CI com bancos sintéticos.
- GitHub branch única, FastAPI único, cluster PostgreSQL AI Studio preservado.
  Não criar segundo app ou segundo banco. Sem reset, push local, limpeza ou merge.
- Cada entrega: commit, PR Draft, 6 jobs, APK com SHA exibido, ZIP fonte,
  validação de assinatura, sync por ff-only no Termux, screenshots e relatório.
- Avisar e preparar handoff de chat antecipadamente, baseado em comprimento
  da conversa; não há medidor exato de limite do contexto.

## Macropacote 120 — 20 verificações (Master SaaS e segurança)
| ID | Entrega / verificação | Prova requerida |
|---|---|---|
| M120-01 | Baseline Git e PR Draft | CI/ref |
| M120-02 | Unicidade da base e do cluster | Termux read-only posterior |
| M120-03 | Inventário por responsável e caixinha | API + Android |
| M120-04 | Busca por nome com argumento SQL parametrizado | Teste backend |
| M120-05 | Busca por identificador UUID com argumento SQL | Teste backend |
| M120-06 | Filtro de status cadastral | API + UI |
| M120-07 | Contagem total de caixinhas do responsável | SQL + parser |
| M120-08 | Contagem ativas | SQL + parser |
| M120-09 | Contagem suspensas | SQL + parser |
| M120-10 | Contagem rascunho inativo | SQL + parser |
| M120-11 | Contagem encerradas | SQL + parser |
| M120-12 | Diferenciar licença registrada de preparação | API + UI |
| M120-13 | Exibir vigência de licença sem data inventada | API + UI |
| M120-14 | Tratar capacidade de membros/cotas separada de caixinhas | UI + contrato |
| M120-15 | Rejeitar campos financeiros/identidade no payload | Parser CI |
| M120-16 | Paginação consistente e sem duplicados | Parser CI |
| M120-17 | Erro/ausência de dados sem fallback demonstrativo | UI + CI |
| M120-18 | Negar acesso para papéis não Master | Teste 403 e RLS |
| M120-19 | Validar integridade de contexto/resposta e regressão auth | CI |
| M120-20 | Compilar APK, sync e homologar no aparelho | CI + operador |
**Critério:** macropacote 120 tem implementação/testes parciais em CI,
mas M120-02 e M120-20 dependem do Termux/aparelho. Não marcar 20/20 agora.

## Macropacote 140 — 20 verificações (acesso único e ciclo do usuário)
1. Inventário de identidades sem PII no Master; 2. estado de autenticação única;
3. troca explícita MASTER/TENANT_ADMIN/TENANT_MEMBER; 4. dois tenants isolados;
5. invalidação de tela em troca de contexto; 6. sessão revogada;
7. expiração; 8. login após segundo plano; 9. lista sessões;
10. logout de contexto; 11. rejeição de refresh fora de ordem;
12. brute-force e rate-limit no CI; 13. vínculo de admin por caixinha;
14. convites como preparação (sem entrega real); 15. aceite simulado de contrato;
16. separação de papéis no PostgreSQL; 17. exceção de suporte mantida 403;
18. testes de concorrência; 19. CI sem vazamentos; 20. APK e homologação.
Nenhuma identidade ou Superuser Master humano será recriada.

## Macropacote 160 — 20 verificações (contribuições e demonstrativos)
1. Leitura por membro; 2. leitura agregada por Admin; 3. Master bloqueado;
4. cota individual; 5. cronograma 2027; 6. valores exatos;
7. pendência; 8. zero pagamento sem conciliação; 9. mora como simulação;
10. extratos; 11. filtros; 12. status; 13. falha offline;
14. mensagens sem lucro declarado; 15. limite por política;
16. RLS; 17. isolamento entre tenants; 18. testes 401/403/503;
19. CI completo; 20. APK/homologação. Sem Pix real.

## Macropacote 180 — 20 verificações (crédito, Price e consentimentos)
1. Price Decimal; 2. primeiro período irregular; 3. ajuste centavos;
4. taxa por política tenant; 5. datas; 6. juros; 7. amortização;
8. saldo final; 9. empréstimos só leitura; 10. bloqueio de desembolso;
11. no autoaprovação; 12. matriz de elegibilidade;
13. consentimento anual puro; 14. revalidação na reserva simulada;
15. concorrência; 16. auditoria; 17. RLS; 18. erro seguro;
19. testes CI; 20. APK/homologação. Nenhum dinheiro real.

## Macropacote 200 — 20 verificações (ledger, encerramento e governança)
1. Ledger DR=CR; 2. FK; 3. idempotência; 4. rollback;
5. multi-tenant; 6. ordens sintéticas; 7. estorno simulado;
8. fechamento prévio; 9. capital-dias; 10. maiores restos;
11. centavos segregados; 12. reserva; 13. 15/85 se aplicável;
14. relatórios; 15. bloqueio liquidação real; 16. backup cifrado;
17. restauração CI; 18. reconciliação pós-restauração;
19. CI; 20. APK/homologação. Liquidação real bloqueada.

## Futuras fases condicionais
- Mercado Pago: conta exclusiva da plataforma + OAuth por tenant, HMAC,
  idempotência, webhook e GET autoritativo, com provedores simulados primeiro.
- Nuvem OCI/GCP, TLS, backup/DR, privacidade e conformidade legal.
- Release Android/iOS, assinatura, rollout e testes de atualização.
- AT-01..AT-50 e matriz de 147 cláusulas com prova integral.
- Liberação real separada por autorização expressa, nunca por PASS da CI.
