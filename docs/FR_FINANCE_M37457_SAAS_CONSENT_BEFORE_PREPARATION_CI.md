# FR Finance M37457 — aceite antes da preparação SaaS (CI estritamente isolada)

## Base

M37456 confirmado no Termux (`8aa1eff`, 59 testes PASS) e no GitHub Actions (6/6 PASS). Banco original, Pix, pagamento, licença e ativação reais não foram modificados.

## Problema corrigido no fluxo lógico

Os recibos sintéticos dos M37455/M37456 foram emitidos **depois** da preparação M30900. O vínculo posterior é útil para testar persistência e idempotência, mas **não pode ser interpretado como consentimento que teria autorizado a preparação original**.

A etapa M37457 torna explícita a ordem contratual exigida para um fluxo futuro:

1. Identidade do administrador lida no servidor, associação ao tenant e sessão ativa.
2. Documento `PLATFORM_LICENSE` publicado, versão e hash íntegros, preço e período selecionados.
3. Apresentação da versão ao titular identificado.
4. Desafio de curta duração, manifestação explícita, recibo único e registro posterior à ação.
5. Pedido de preparação **posterior ao registro do recibo**.
6. Preparação posterior ao pedido, sem pagamentos, licenças nem ativação por inferência.

## Código

- `backend/app/saas_preparation_chronology_ci.py`: política pura, imutável e *fail-closed*; valida identidade, valores, documento, horários com timezone, validade do desafio, anti-replay e ausência de registros financeiros. O retorno positivo é somente `CI_PREPARATION_CHRONOLOGY_CONSISTENT_NOT_AUTHORITY`.
- `backend/scripts/aistudio_m37457_chronology_readback_ci.py`: consulta exclusivamente o PostgreSQL de GitHub Actions `frcaixinha_staging` na porta 5432, com `default_transaction_read_only=on`; prova que a cadeia M30900/M37455/M37456 **continua bloqueada como evidência de aceite prévio**. Sem gravações.
- `backend/tests/test_m37457_preparation_chronology_ci.py` e `backend/tests/test_m37457_chronology_readback_ci.py`: casos positivos **hipotéticos** e testes adversariais (sessão adulterada, reuso, digest incompatível, apresentação antecipada, janela expirada, troca de caixinha/administrador/preço, preparo antecipado).
- `backend/scripts/aistudio_staging_chain_ci.sh` executa a auditoria de leitura após M37456 no banco descartável; `.github/workflows/validacao-atualizacao.yml` executa testes estáticos/política.

## Estado real versus CI

Embora o motor use rótulos como `CI_SYNTHETIC_SERVER_SESSION_READBACK`, **nenhum dado da interface ou teste prova a identidade real de alguém**. Os resultados nunca atestam:

- identidade pessoal, posse de e-mail ou validade legal do aceite;
- assinatura eletrônica juridicamente comprovada;
- existência de assinatura SaaS paga, ordem ou fatura;
- concessão de licença, habilitação de usuários ou Pix real;
- configuração ou disponibilidade de infraestrutura OCI.

Todos os campos de autorização real permanecem `false`. O M37457 não cria tabelas, migrações, endpoints, licenças nem cobranças. O catálogo SQL original continua com 106 arquivos.

## Próxima fase técnica

Para preparar um onboarding comercial efetivo, será necessário implementar um **endpoint autenticado** e uma gravação transacional de aceite *antes* da preparação, com sessão de usuário verificada no servidor, consentimento explícito, assinatura/registro imutável, revalidação do texto canônico e prevenção de replay no banco de dados, seguidos por comprovação independente de pagamento e emissão idempotente de licença. Tudo isso depende de validação e implantação controlada em OCI.

## Execução local segura

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37457_preparation_chronology_ci.py backend/tests/test_m37457_chronology_readback_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não execute** a rotina de banco descartável `aistudio_staging_chain_ci.sh` nem o executável `aistudio_m37457_chronology_readback_ci.py` no celular.
