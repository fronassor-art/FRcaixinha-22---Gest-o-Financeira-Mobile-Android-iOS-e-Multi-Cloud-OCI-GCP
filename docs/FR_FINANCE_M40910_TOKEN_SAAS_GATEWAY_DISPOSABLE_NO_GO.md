# FR Finance M40910 — leitura SaaS por token opaco sem GUC em PostgreSQL descartável

**Base:** M40900 `3b9b1c3` sincronizado no Termux nativo pelo operador, `NO_SCHEMA_DELTA`, nenhuma migração/ACL ou reinício no banco original. PR #2 segue Draft.

## Objetivo e escopo

Na CI PostgreSQL 18 descartável `127.0.0.1:55433/fr_m39067_disposable_ci`, a fixture primeiro executa M40900: reproduz GUC spoof e revoga do papel app SELECT, INSERT por coluna e EXECUTE de SQL113. O novo broker experimental, de propriedade de role `NOLOGIN` sem filiação ao app, tem SELECT apenas para construir resposta SaaS publicada e conferir estado de tenant/sessão. Ele usa `SECURITY DEFINER SET search_path=pg_catalog,pg_temp`, com função de parâmetros tipados e SHA-256 do token opaco. O chamador app não pode consultar diretamente tabelas SQL113, tokens, assumir role broker ou executar a função legada.

O broker verifica pelo SQL a sessão sintética: token válido, vínculo TENANT_ADMIN no tenant solicitado, tenant ativo com mesmo administrador, validade, ausência de revogação e ausência de preparação/licença SaaS existente. A consulta retorna somente a última revisão vigente e publicada de cada campanha, sem aceitar `app.current_*` como autoridade. Testa leitura por dois administradores legítimos, GUC Master falsificado, membro, tenant errado, token expirado/revogado/aleatório, alteração de adesão e revogação ativa.

**Importante:** este é **somente um protótipo isolado**, não modifica `backend/app/routers/saas_promotions.py`, `get_current_session`, `get_rls_db_connection`, SQL113 histórico ou banco original. A função é criada unicamente no runner descartável; não há nova migration. O backend real continua usando caminhos GUC vulneráveis.

## Riscos e limitação de desenho

- Uma pessoa que roube o **token opaco válido** ainda possui capacidade de leitura até revogação/expiração; exigem-se binding de dispositivo/sessão, proteção contra replay, logging e rate limits.
- A role broker tem visibilidade interna de linhas de promoções no banco descartável; se sua autoridade ou SQL de função for comprometida, os limites mudam. O ambiente real requer custódia, papéis/ACL e auditoria independente.
- Este broker é **somente leitura**, não restaura funções Master de draft, publicação/cancelamento nem escrita auditada; a revogação M40900 as interromperia. Não se pode aplicar o fence à produção antes de substituí-las.
- Não repara M40730 (login SQL emissor roubado), M40570 (GUC nos caminhos restantes), nem o risco de SQL proprietário/superuser ou rotas legadas; nenhuma prova real de RLS foi feita no Termux.
- O teste físico do Android M40860, processo FastAPI `NOT_ATTESTED`, OCI, Vault/KMS/TLS, PSP e revisão jurídica continuam pendentes.

Somente após desenho de todas as rotas de leitura/escrita e autorização independente, ensaio de migração reversível, backup/restauração e aprovação expressa, considerar SQL novo. **Nenhuma migração é indicada por este pacote.**

`MIGRATIONS=NONE`; `ORIGINAL_DB_CONNECTIONS=NONE`; `LOCAL_DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`. **NO-GO**.
