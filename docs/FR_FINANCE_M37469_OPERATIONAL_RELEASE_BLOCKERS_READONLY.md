# FR Finance — M37469 | Bloqueios operacionais para lançamento (somente leitura)

## Ponto de partida

O M37468 está homologado no Termux: commit `0efe6ea`, 122 testes locais aprovados, versão SQL com 106 arquivos íntegros e banco local preservado. A cadeia GitHub aprovou a auditoria de oferta congelada, recibo, pós-revogação, RLS e PostgreSQL descartável. **Nada disso prova identidade ou consentimento de usuários reais**, autorização de assinatura ou acesso autorizado a Pix.

## Objetivo

Parar de repetir somente testes sintéticos e transformar as pendências restantes em uma fila objetiva de **comprovações externas reais**, sem inventar status de provedores nem usar informações privadas. M37469 não é um motor de liberação comercial; é um relatório **fail-closed** e auditável.

## Implementado

- `backend/app/saas_operational_blockers_m37469.py` reutiliza as **20 exigências do inventário já existente**, `backend/app/release_evidence_matrix.py`. Não cria uma segunda lista divergente. Agrupa em identidade E2E, aceite contratual, OCI/infra, entrega de e-mails e pagamentos. Mantém os **sete gates de provedores externos**.
- Confere a presença e calcula o hash SHA-256 **de código-fonte** dos 12 arquivos de testes dos 11 macropacotes M37458–M37468. **Hash de arquivo não comprova que um teste passou**; a validação efetiva continua sendo a CI, e nenhum deles é uma atestação operacional.
- Mantém `live_gates_verified=0`, `provider_gates_verified=0`, `production_authorized=false` e `staging_deployment_authorized=false`, independentemente de flags do ambiente, existência dos arquivos ou `ENVIRONMENT=production`. Não oferece um atalho de ativação.
- Classifica apenas **nomes conhecidos de flags** como `DECLARED_OFF`, `NOT_DECLARED` ou `NON_OFF_DO_NOT_DEPLOY`; não grava nem imprime segredos, senhas, DSNs, OCIDs sigilosos ou valores de tokens.
- `backend/scripts/aistudio_m37469_release_blockers_readonly.py` é um relatório de linha de comando sem operações de rede, banco, alteração de flags, Git push, OCI launch ou pagamento; aceita `audit`, `plan` e `json`.

A suíte `backend/tests/test_m37469_release_blockers_readonly.py` verifica os 20 bloqueios, sete provedores, 11 pacotes, troca de hashes, arquivos ausentes/symlinks, flags perigosas e ausência de elevação acidental a autorização. O GitHub Actions executa os testes e a apresentação do plano.

## Ordem prática das próximas comprovações

| Prioridade | O que falta provar no ambiente apropriado |
|---|---|
| 1. OCI compute | Confirmar VM realmente `RUNNING` na região `sa-saopaulo-1`; uma VCN pronta **não** substitui a VM |
| 2. API e banco OCI | HTTPS/DNS válido, Vault/IAM, PostgreSQL com TLS/RLS, migrações versionadas, backup/restauração e SHA da API |
| 3. Autenticação | Login real de contas de teste, posse do e-mail, rotação/revogação de sessão, Master MFA e dupla aprovação |
| 4. Contratos | Documento jurídico final publicado, integridade de bytes, aceite expresso **do próprio usuário** e trilha protegida |
| 5. E-mail | SPF, DKIM, DMARC, Brevo/SMTP em ambiente autorizado, outbox e fluxos de expiração/recuperação |
| 6. Mercado Pago Connect | Redirect HTTPS, PKCE/state, refresh segregado por administrador, callback e credenciais no Vault |
| 7. Pix entrada | Orders/webhook assinado, pagamento de teste e conciliação PSP ↔ app ↔ Livro-Razão |
| 8. Pix saída | Autorização comercial expressa, limites e controles, sem suposição de acesso à Money Out |
| 9. Android | APK/AAB de release assinado, atualização no aparelho e correspondência de versão com a API |

Nenhum desses itens recebe status de verificação real por estar listado. O M37469 **não consulta** o estado atual da VM; o monitoramento OCI continua sendo um fluxo separado.

## Como usar no Termux com segurança

```bash
cd "$HOME/fr-finance"
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37469_release_blockers_readonly.py
python backend/scripts/aistudio_m37469_release_blockers_readonly.py audit
python backend/scripts/aistudio_m37469_release_blockers_readonly.py plan
python backend/scripts/aistudio_migration_inventory.py repo-check
```

O comando `json` gera uma saída estruturada sem segredos para acompanhar os gates; os **hashes de código não substituem um resultado de CI**. O relatório não lê os provedores, não altera o banco original ou OCI, não movimenta dinheiro nem liga o Pix.

## Critério para o próximo macropacote

M37470 deverá começar a trabalhar nos **bloqueios operacionais concretos**, com prioridade para inspeção somente leitura da infraestrutura OCI e preparação do teste E2E de identidade/aceite em staging. Não criar licenças ou ativar membros sem provas reais aprovadas.

### Conclusão de segurança

`PRODUCTION_RELEASE=BLOCKED`; `REAL_ACTIVATION_AUTHORIZED=NO`. Identidade real, consentimento legal, publicação OCI, pagamentos conciliados e permissões de saída Pix permanecem pendentes de evidência independente.
