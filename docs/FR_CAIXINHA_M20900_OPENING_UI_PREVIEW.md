# AI Studio M20900 — Prévia no Android

Adicionada a tela "Preparar novo ciclo" no perfil administrador, acessível pela aba Contribuições.
O administrador informa ano, valor e justificativa, com valor mínimo de R$ 150,00. O backend valida o vínculo, o ciclo existente e as condições de abertura.
Sem geração de valores padrão, sem alteração dos 12 débitos históricos e sem acesso Master/Membro.
A API retorna apenas prévia, sempre com cycle_creation_enabled=false, até ser homologada uma rotina atômica de criação com idempotência e auditoria no PostgreSQL.
Nenhum banco local é modificado por este pacote. Não reiniciar a API sem sincronizar os commits.
