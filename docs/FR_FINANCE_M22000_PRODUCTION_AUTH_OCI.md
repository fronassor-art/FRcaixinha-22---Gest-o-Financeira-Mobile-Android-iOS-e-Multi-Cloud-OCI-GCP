# M22000 — Contrato técnico para autenticação de produção na OCI

O backend AI Studio não deve ficar permanentemente incapaz de login de produção. Este pacote adiciona um gate estrito que exige configuração EXPLÍCITA antes de ativar a comunicação da autenticação com o banco OCI:

- ENVIRONMENT=production e FR_FINANCE_AUTH_PRODUCTION_GATE=OCI_STAGING_REVIEWED
- APP_URL HTTPS pública, nenhum Termux ou FRCAIXINHA_TEST_AUTH em produção
- AUTH_SECRET e AUTH_RATE_LIMIT_HMAC_KEY com ao menos 32 bytes, distintos
- três identidades PostgreSQL: frc_ai_app, frc_ai_auth, frc_ai_verifier
- mesmo banco de produção, DNS, porta 5432 e sslmode=verify-full
- papel de superusuário, conexões locais e bancos de desenvolvimento recusados

Nada disso foi configurado no ambiente do operador. O gate está DESATIVADO por padrão. O retorno PRODUCTION_CONFIGURED_UNVERIFIED não é prova de funcionamento do servidor ou de segurança do DB.

Antes de habilitar este gate é OBRIGATÓRIO: provisionar OCI staging; implementar verificações online de roles sem SUPERUSER/BYPASSRLS, grants, FORCE RLS e função emissora de sessão; validar certificados reais; configurar cofre/backup; simular três perfis e isolamento entre tenants; homologar autenticação e revisão de segurança independente.

Não colocar senhas/DSNs/tokens em logs, GitHub ou no chat. Nenhuma VM, API pública, operação Pix real, lançamento ou conciliação financeira foi ativada por M22000.


## M40958 — segregação de credenciais e identidade de destino

O gate M22000 passa a rejeitar nomes DNS ambíguos, destinos múltiplos,
identidades codificadas e senhas inválidas depois de decodificar o URI.
Os três papéis SQL e as duas chaves de autenticação devem usar cinco
segredos distintos, inclusive quando uma senha aparece codificada.
Nenhum segredo é incluído na representação do objeto ou nas recusas.
Os testes usam credenciais sintéticas e não conectam ao banco ou provedor.
A aprovação continua exclusivamente sintática e não equivale a homologação
de autenticação, custódia, RLS, TLS ou autorização de produção.


## M40959 — sintaxe inequívoca e flags de homologação

O gate de autenticação exige o subconjunto URI PostgreSQL estrito: porta
literal 5432, parâmetro literal sslmode=verify-full, sem aliases de query,
e senha ASCII não reservada ou com caracteres reservados codificados em
percentual UTF-8. A comparação continua sendo dos valores decodificados.
A origem pública deve ser ASCII, canônica, com rótulos DNS válidos e
sem delimitadores vazios, caracteres de controle ou portas alternativas.
As flags de teste e Termux só admitem ausência, vazio ou 0 em produção.
As recusas são genéricas e não exibem credenciais. Os testes são sintéticos,
sem conexões. Não há homologação de DNS, TLS, driver, custódia, RLS ou
produção real por este pacote. Nenhuma migração ou ativação é autorizada.


## M40960 — origem HTTPS compartilhada e CORS

O validador compartilhado de origem pública rejeita aliases IPv4 de navegador
(inclusive formatos abreviados, octais ou hexadecimais com rótulo final
numérico), caracteres de controle, Unicode não codificado, rótulos DNS
longos, barras invertidas e delimitadores vazios. A autoridade aceita
somente porta ausente ou 443 literal. CORS de produção fica vazio para
origens inválidas; o gate de autenticação permanece mais estrito quanto
à forma canônica. Não há resolução DNS, teste de TLS ou rede real.
