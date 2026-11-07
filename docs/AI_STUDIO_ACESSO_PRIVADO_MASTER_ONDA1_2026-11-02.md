# Onda 1 — entrada privada do proprietário
Data: 02/11/2026. Escopo: FRcaixinha AI Studio Mobile, sem outros projetos.

## Funcionalidade
O login público mostra Administrador e Membro. O formulário Master é
reservado, aberto com sete toques no logotipo da tela de entrada dentro de
quatro segundos ou, no web app, pelo fragmento local
`#/acesso-proprietario`. Não há botão Master na tela pública.

O gesto e o endereço não são fatores de segurança e podem ser descobertos.
O acesso depende exclusivamente do backend FastAPI/PostgreSQL: senha,
rate limiting, status da identidade, papel MASTER, is_master verdadeiro,
tenant_id nulo, sessão ativa e RLS. Nenhum segredo foi embutido no cliente.

Após o login, o cliente verifica a sessão no endpoint
`GET /api/v1/master/owner-access`, protegido por `require_master`.
O painel só é exibido após resposta válida. Em falha o token provisório
é enviado para revogação, sem ser armazenado no estado do aplicativo.

## Conexão com próximos pacotes
A gestão de administradores deverá utilizar os endpoints de governança
Master existentes: `/api/v1/master/overview`, licenças e auditoria.
O fluxo de convite administrativo ainda está indisponível e depende de
implementação transacional, aceite e verificação antes de uso.
Nunca permitir ao Master acessar saldos ou dados particulares dos membros.
Não ativar pagamentos, migrações reais ou provisionar contas Master.

## Limites e próximos bloqueios
MFA obrigatório com inscrição, recuperação e rotação segura do dispositivo
ainda NÃO existe. Exige implementação e revisão antes de qualquer uso
em produção. Homologação não equivale a autenticação de produção.
A assinatura Android e a branch main permanecem intactas.
