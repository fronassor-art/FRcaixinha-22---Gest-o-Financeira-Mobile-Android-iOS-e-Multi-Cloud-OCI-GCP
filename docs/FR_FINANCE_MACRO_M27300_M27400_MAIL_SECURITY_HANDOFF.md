# FR Finance AI Studio — Macropacote M27300–M27400

## Entrada

M27106 validada: commit `2da38d9`, 6/6 jobs GitHub e 91 SQL.
A M27200–M27210 foi sincronizada no Termux até `1c5de90`
e tem workflow `42395309826` com sucesso. O retorno fornecido
comprova `git pull --ff-only`, **não a execução de testes locais
da M27200**. A branch continua `atualizacao-ai-studio-9b46a63187`,
PR #2 aberta em rascunho.

## M27300 — índice opaco de destinatário com HMAC

`backend/app/recipient_index_guard.py` oferece a interface para o
**índice futuro de destinatário em banco**, sem persistir dados.
O digest é HMAC-SHA256 com separação de contexto por tenant UUID e
uma chave exclusiva por serviço (`load_index_key`). Nunca reutilizar
a chave AES-GCM do envelope; o índice SHA-256 de e-mail existente no
staging M25900 continua apenas legado até uma migração própria.

O módulo valida formato de e-mail sem cabeçalhos, alias de chave,
UUID, chave de 32 bytes, versão e integridade do índice. Usa
`hmac.compare_digest` para comparação; não devolve e-mail em
`repr` e não obtém segredos por rede, disco, variáveis de ambiente
ou rotas públicas.

**Limitação:** padroniza o e-mail em minúsculas para compatibilidade
com o índice legado. Domínios de e-mail não diferenciam maiúsculas,
mas partes locais podem depender do provedor; definir essa política
antes de uso real. A implantação do HMAC no banco real, estratégia de
rotação por tenant, acesso do trabalhador e reindexação de históricos
ainda NÃO ocorreram.

## M27400 — confirmação de gravação do desafio antes do transporte

`backend/app/committed_challenge_handoff.py` compara o desafio
preparado M27200 com uma fotografia de leitura do SQL M27100,
exigindo identidade do tenant, evento, documento, digest do desafio,
controle de uso, tentativas, estado, prazo, ausência de quarentena
e proveniência CI. O retorno é sempre
`CI_CHALLENGE_READBACK_MATCHED_NO_SEND`.

`SyntheticChallengeReadback` **não é uma credencial ou prova assinada**.
Um atacante pode construir um objeto Python; em produção será
necessário obter a leitura diretamente de uma conexão PostgreSQL
autenticada e transação confirmada, por uma role segregada, sem
aceitar entradas HTTP como prova. Nem esse objeto nem o resultado
autorizam o envio; `can_send_network=false`.

## Proteções e verificação

Testes `test_m27300_recipient_index_guard_ci.py` e
`test_m27400_committed_challenge_handoff_ci.py` cobrem:
- isolamento por tenant e troca/revogação de chave indexadora;
- prevenção de indexação de endereços inválidos e exceções genéricas;
- comparação HMAC, integridade do digest, UUIDs e versão;
- desafio consumido, token adulterado, conflito de contrato,
  prazo vencido, excesso de tentativas, quarentena e estado não
  autorizado;
- ausência de envio SMTP, de escrita em banco ou de nova rota pública.

Ambos fazem parte da suíte obrigatória da API no GitHub Actions.

## Matriz de conclusão: pendências sem mascarar bloqueios

- **Feito em código de CI:** AES-256-GCM M26400, fila com lease e
  quarentena M26600, envelope staging M26700, política e adaptador
  OCI Vault simulado M26800–26900, desafio sintético M27100–27106,
  ponte M27200 e controles de HMAC/readback deste pacote.
- **Ainda sem comprovação operacional:** OCI provisionada, IAM e Vault
  reais, migrações homologadas no banco de staging de produção,
  remetente e domínio verificados, SPF/DKIM/DMARC, credenciais de
  provedor de e-mail, worker seguro, callback assinado e reconciliação
  de resposta ambígua.
- **Ainda bloqueado por falta de integração real:** convite público,
  recuperação de senha, prova de titularidade do e-mail, aceite do
  termo canônico pela pessoa convidada, MFA e dupla aprovação,
  fechamento financeiro e Pix real.

É incorreto interpretar testes sintéticos como aprovação para criar
administradores ou membros reais. A M27400 não abre os gates e
não modifica Master, contratos, usuários, caixa ou pagamentos.

## Regras de operação no Termux

Apenas sincronizar e rodar pytest, `repo-check` e
`bash -n` após o commit e CI divulgados.
**Não** aplicar SQL do staging/CI ao PostgreSQL 18 na porta
`5433`. A quantidade permanece em **91 SQL versionados** e
`FR_FINANCE_PIX_REAL=DESATIVADO`.

O próximo objetivo operacional é obter domínio/conta de e-mail,
identidade OCI real e autorização expressa de migração staging,
para adaptar a API ao provedor escolhido sem prometer entrega antes
de testes externos.
