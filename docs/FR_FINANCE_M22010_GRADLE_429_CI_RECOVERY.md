# M22010 — Resiliência GitHub Actions Gradle frente a Maven Central 429

No run 42263799978, o GitHub Actions falhou na etapa assembleDebug porque repo.maven.apache.org devolveu HTTP 429 Too Many Requests para múltiplas dependências, incluindo com.squareup:javawriter e jsr305. Os outros cinco jobs (frontend, FastAPI, PostgreSQL/RLS, PostgreSQL 18 e ZIP) passaram.

Correção: concurrency por PR com cancel-in-progress, cache de dependências por gradle/actions/setup-gradle@v4, e até 3 tentativas de Gradle apenas quando o log contiver HTTP 429. Outros erros de compilação/assinatura falham imediatamente, sem mascarar defeitos do projeto. Idêntica resiliência no workflow de APK remoto futuro. Não reduz a proteção de assinatura nem habilita dinheiro real.

Este ajuste de CI não comprova instalação Android nem implantação OCI. Nenhum token foi exposto ou VM criada.
