# M21900 — APK de homologação remota para OCI (sem VM)

Fluxo manual de GitHub Actions preparado: recebe uma URL HTTPS da API em staging OCI, valida perfil do Capacitor, compila APK debug assinado da frente AI Studio e publica artefato temporário. Nunca inclui token Mercado Pago, Pix real ou senha de banco.

Somente acionar após provisioning de staging OCI, HTTPS válido, credenciais de assinatura já existentes e teste de autenticação em staging. O APK terá sufixo .aistudio e não é release comercial. Nenhuma VM foi criada, nenhum webhook foi registrado, nenhum dinheiro foi movido.

IMPORTANTE: workflow_dispatch pode não estar disponível na interface até o workflow existir na branch principal; isso não autoriza mesclar a PR #2 sem homologação.

A faixa Always Free descrita pela OCI em 06/11/2026 é equivalente a 2 OCPUs e 12 GB RAM de Ampere A1, além de 200 GB em volumes na região home. Verificar cotas, capacidade e preço efetivos antes de contratar qualquer recurso.
https://docs.oracle.com/pt-br/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
