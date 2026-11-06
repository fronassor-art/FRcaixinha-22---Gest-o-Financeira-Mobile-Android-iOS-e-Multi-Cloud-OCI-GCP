# M23500 — Persistência OAuth com consentimento e revisão protegida

Pacote de preparação, desativado por padrão. Implementa o contrato de um sink para as credenciais Mercado Pago por caixinha. Antes da gravação de tokens, consulta vínculo tenant, ator e seller; grava uma revisão protegida pendente por adaptador injetado; verifica novamente o consentimento; e só informa êxito quando o registro confiável confirmar a revisão por compare-and-swap (CAS). Em erro, tenta cancelar apenas a nova revisão, preservando a credencial anterior.

ATENÇÃO: a segunda verificação prévia não assegura atomicidade. A implementação real do CAS no PostgreSQL precisa revalidar consentimento, revogação, seller e versão anterior dentro da transação. O cancelamento de uma revisão em OCI Vault não equivale a destruição instantânea e deve ser auditado. Vault e PostgreSQL não participam da mesma transação distribuída.

A interface admite uma versão persistente por seller, ou criptografia de envelope com chave do OCI KMS. Nunca usar um novo segredo OCI por cada tentativa OAuth sem confirmar custo, limites, expiração e compensação. Não há adaptador operacional de escrita OCI neste pacote.

Testes apenas sintéticos. Nenhuma rota pública, operação Mercado Pago, migração do Termux, segredo real ou transação financeira.
