# FR Finance M37447 — teste físico do APK: pré-diagnóstico de conexão

O checkpoint M37446 passou no Termux com 23 testes de API, teste Node da
interface e PostgreSQL original READ_ONLY_PASS. Nenhuma abertura de ciclo,
Pix ou ativação real foi feita.

**Diferença crítica de ambientes:** a compilação Android automática do
workflow validacao-atualizacao.yml usa o perfil debug local com
VITE_API_URL=http://127.0.0.1:8000. No APK Android esse IP indica o próprio
smartphone, NÃO a OCI. O APK consegue ser instalado mesmo sem servidor
acessível; o login não pode ser homologado só com um build 6/6 PASS.

Para conectar a OCI quando existir HTTPS, o workflow separado
fr-finance-oci-staging-apk.yml exige entrada HTTPS e assinatura persistente,
sem incluir 127.0.0.1. NÃO iniciar esse build com URL inventada.

O pacote M37447 inclui um diagnóstico na tela de login do próprio
APK, sem credenciais ou tokens: identifica modo local, HTTPS remoto ou
configuração inválida, e permite consultar manualmente somente
GET /api/v1/auth/status. Uma resposta de status não representa login real,
não verifica Pix e não ativa nenhum membro. A classificação da API
NUNCA imprime URL completa, query strings, tokens ou segredos.

Testes CI de perfis Android local/HTTPS e falhas de URL, configuração,
autenticação e interface. O banco do Termux permanece intacto.

Homologação manual posterior: instalar o APK do workflow aprovado,
abrir o app e observar o status de API; não fornecer credenciais reais
até existir backend confiável e configuração de segurança validada.
O teste real de administrador e abertura de ciclo permanece separado.
