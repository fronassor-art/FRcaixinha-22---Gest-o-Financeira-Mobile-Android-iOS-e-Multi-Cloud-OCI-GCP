# FRcaixinha AI Studio — Macropacote 280: observabilidade do runtime local

## Objetivo
Após a homologação do APK 208 (8/8 PASS informados pelo operador), sincronização ff-only do M260 e reinicialização manual do FastAPI, o objetivo é reduzir ambiguidades entre *código no disco* e *código realmente carregado* pelo Uvicorn. Exclusivamente projeto AI Studio Mobile, não FRcaixinha 2.2.

## Alterações restritas
- Corrige o identificador legado do aplicativo no endpoint `/api/health`.
- Introduz `GET /api/health/runtime`: responde somente metadados estáticos e os limites de leitura contábil importados pelo **processo Python em execução**.
- Marca fechamento, conciliação e verificação de SHA Git como `false`.
- Não expõe credenciais, URLs do banco, usuários ou dados financeiros e usa `Cache-Control: no-store`.
- Script `backend/scripts/aistudio_280_runtime_readonly.sh SHA_COMPLETO`: exige Git local alinhado, PG18 AI Studio porta 5433, API ready HTTP 200 e contrato de runtime M280 exato.
- Novos testes FastAPI e sintaxe Bash na CI. Nenhuma migração, criação de conta, reinicialização automática ou escrita em PostgreSQL.

## Procedimento
1. Confirmar CI 6/6 PASS e PR #2 Draft sem merge.
2. Sincronizar Git por fast-forward protegido para o SHA aprovado.
3. **Reiniciar somente o FastAPI manualmente** com Ctrl+C no terminal da API; depois `bash backend/scripts/run_termux_fastapi.sh`, preservando o PostgreSQL 5433.
4. Em outra sessão Termux, executar `bash backend/scripts/aistudio_280_runtime_readonly.sh SHA_COMPLETO`.
5. Verificar APP, Admin, Master e Membro no APK correspondente se houver alteração de frontend ou de build. Não chamar homologado antes da confirmação do operador.

## Limitações e pendências preservadas
A assinatura de runtime prova que o processo carregou a implementação deste endpoint e lê os limites importados pelo módulo Ledger; **não comprova que todo o commit Git foi executado**. A CI valida código do commit, mas não a segurança financeira de produção.

- Backup cifrado: criado, SHA-256 validado, restauração em cluster descartável e limpeza PASS segundo o operador; **cópia off-device da chave age e do backup ainda não comprovada**.
- Recuperação funcional completa, RPO/RTO, linhas e integridade referencial pendentes.
- RLS: faltam testes locais autenticados das contas técnicas app/auth/verifier, sem tocar nos dados reais.
- Livro-Razão: limites de segurança M260 provisórios; paginação e extrato por conta, filtros, competência, auditoria imutável, reconciliação e completude são pendentes.
- Fluxos de empréstimos, pagamentos Pix/Mercado Pago, 15/85, fechamento e dinheiro real permanecem bloqueados, sem aprovação operacional.
- Identidade Master única, SaaS, convites, LGPD, contratos, OCI/GCP, deploy e disponibilidade.
- GitHub PR #2 Draft, `main` intacta; comparação AI Studio posterior, nenhum upload agora.
