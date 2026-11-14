# FR Finance — M39002 | Dados privados no Android, sem depender de OCI

## Checkpoint confirmado

O M39001 terminou no Termux com **11 testes PASS**, banco original `frcaixinha_aistudio_dev` na porta 5433 e funções 047/048 atestadas com `frc_ai_auth`. A FastAPI original carrega as quatro rotas de acesso, mas o fluxo de entrega e recuperação permanece **DESATIVADO**; `APP_URL` de produção retornou `HTTPS_UNREACHABLE_OR_UNVERIFIED`. O M39000 foi homologado por 13 testes locais e CI do GitHub. Não repetir cadastro Brevo, SQL 047/048, PostgreSQL, diretórios ou servidores.

## Problema real tratado sem VM

No Android nativo o `AndroidManifest.xml` tinha `android:allowBackup="true"`. O aplicativo gerencia sessões, estados de conta e informações financeiras, portanto cópias automáticas e migração entre dispositivos podem transportar dados que deveriam ser revalidados junto à API.

M39002 altera **apenas recursos Android e testes**:

- `android:allowBackup="false"` no mesmo aplicativo, sem mudar `applicationId` ou a chave de assinatura;
- `android:fullBackupContent="@xml/full_backup_rules"` com exclusões de arquivos, banco, preferências, raiz e dados externos para o legado Android 11 ou anterior;
- `android:dataExtractionRules="@xml/data_extraction_rules"` com exclusões equivalentes em **cloud-backup** e **device-transfer** no Android 12 ou posterior;
- `backend/tests/test_m39002_android_private_data_backup_ci.py` e um job CI que impedem a reintrodução acidental de backup e também verificam a assinatura release, o ID do pacote e a política HTTPS já existente.

O código **não compila nem assina** APK release e não garante que todos os fabricantes de Android implementem o controle exatamente da mesma forma; o manifesto mesclado e o dispositivo final precisam de homologação. O `applicationId` principal foi mantido para evitar ruptura na trajetória de atualização do app; o APK de teste continua segregado pelo sufixo `.aistudio`.

## O que permanece pendente

- Registrar o servidor real e confirmar HTTPS, TLS, conteúdo da aplicação, associações Android App Links e assetlinks.json com o certificado de assinatura **real**.
- Compilar, assinar e instalar uma **nova versão** de release com a política final; verificar backup/migração no dispositivo antes da publicação.
- Ativar worker Brevo apenas após URL HTTPS funcional, destinatário de homologação consentido, prova de entrega e autorização operacional.
- Homologar Mercado Pago Connect, Orders Pix e Money Out com provas reais do provedor. **Pix real OFF** e ativação de membros reais **OFF** até liberação.

M39002 não aplica migração SQL, não cria banco, não reinicia FastAPI, não envia SMTP, não cria VM e não movimenta dinheiro.
