# FR Finance — M40740: bloqueio explícito do transporte Pix real (NO-GO)

**Base:** M40730 (emissor SQL e GUC ainda não remediados). **Escopo:** somente o adaptador `backend/app/mp_pix_execution.py`, código-fonte e CI offline. Não é liberação de produção.

## Mudança

A função interna `_send` recusa qualquer transporte que não seja **exatamente** `httpx.MockTransport`, incluindo ausência de transporte, `httpx.AsyncHTTPTransport`, transportes personalizados e subclasses de MockTransport. A função `_client` aplica a mesma restrição, evitando que um chamador pule a validação da primeira função. O parâmetro antigo `approved_network=True` não libera I/O externo. Os testes sintéticos continuam utilizando `httpx.MockTransport` e não fazem chamadas de rede.

O bloqueio é **defesa de profundidade localizada neste adaptador**, não um firewall geral, não audita outras integrações financeiras, não impede código malicioso de fazer rede por outras bibliotecas e não prova a segurança da função de callback do mock. A aplicação em memória no aparelho não recebe esta mudança até sincronização de código e reinicialização formalmente autorizada; não executamos nenhuma dessas ações aqui.

## Segurança ainda pendente

- **M40730 SQL signer:** comprometimento do login do emissor permite tickets sem verificar Ed25519 HTTP. **NO-GO**.
- **M40570 GUC:** contexto `app.current_*` pode ser falsificado por SQL arbitrário como papel app. **NO-GO**.
- Faltam custódia externa de chaves, segregação operacional, TLS/HTTPS atestado, identidade de processo, Android Keystore/enrollment, recuperação de dispositivo e testes integrados de staging.
- Nenhum teste offline confirma capacidade de Pix, homologação do Mercado Pago, conciliação financeira ou autenticação física do usuário.

## Validação

A suíte `backend/tests/test_m40740_pix_network_no_go_ci.py` executa apenas AST isolada das duas funções, sem importar/iniciar FastAPI nem serviços, e verifica cenários positivos apenas com mock e negativos com transporte ausente, de rede e personalizado. O workflow instala somente pytest/httpx em runner GitHub; não possui PostgreSQL, credenciais, túnel, SSH nem deploy.

**Restrições mantidas:** nenhum acesso ao PostgreSQL original `frcaixinha_aistudio_dev:5433`, sem migração, sem criação ou escrita de banco local, sem restart de FastAPI/PostgreSQL, sem envios, PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED. PR #2 permanece Draft e main preservada.

**Critério de reversão futura:** revisão de arquitetura, provas independentes para o emissor SQL/GUC, autorização explícita de release e novo commit auditado. Nunca desbloquear rede real apenas por variável de ambiente ou resposta do cliente.
