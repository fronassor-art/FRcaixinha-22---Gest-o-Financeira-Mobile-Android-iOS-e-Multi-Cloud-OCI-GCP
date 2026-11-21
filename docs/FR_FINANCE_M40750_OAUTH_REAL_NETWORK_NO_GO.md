# FR Finance — M40750: OAuth Connect sem tráfego real (NO-GO)

**Base auditada:** M40740 `318a553`, após sincronização source-only no Termux atestada pelo operador. Este documento NÃO comprova qual versão do FastAPI está em memória no aparelho.

## Por que este pacote existe

M40740 tornou o adaptador Pix `mp_pix_execution.py` mock-only, mas a implementação separada de OAuth Connect `mp_connect_http_runtime.py` ainda permitia `httpx.AsyncClient(transport=None)` quando `real_https_authorized=True`. O fluxo pode trocar ou renovar credenciais contra `https://api.mercadopago.com/oauth/token`. Mesmo não sendo uma transferência financeira, a emissão de tokens reais não foi homologada; manter tal opção aberta contrariaria as restrições do laboratório.

## Alteração de código-fonte (não implantada no FastAPI)

A função `_send_token_post` exige agora `type(transport) is httpx.MockTransport` antes de criar qualquer cliente HTTP. `real_https_authorized=True` sozinho não libera rede, assim como uma instância `AsyncHTTPTransport`, subclasses ou transportes personalizados. O teste preserva a serialização JSON e valida a resposta de OAuth **sintética**, sem ativar o provedor.

O escopo é este adaptador. Não é firewall do SO, não isola outras integrações, não impede callback de mock de realizar operações próprias e não confirma credenciais reais. O proprietário do código ainda deverá auditar outros caminhos de saída antes de produção.

## Bloqueios de arquitetura preservados

- **M40730:** credencial SQL do emissor comprometida ainda emite tickets fora da verificação Ed25519 (**NO-GO**).
- **M40570 / GUC:** executores SQL arbitrários com papel app podem falsificar `app.current_*` (**NO-GO**).
- Faltam HTTPS real atestado, custódia Vault/KMS, enrollment de chaves, proteção de secrets, provas de isolamento operacional e testes completos no staging.
- Nenhuma aprovação para OAuth real, Pix real, conciliação ou ativação foi concedida.

## CI e ambiente

A CI específica roda somente em runner GitHub, sem PostgreSQL, variáveis de credenciais de provedor, serviço FastAPI ou deploy. Valida transporte ausente, transporte HTTP real, personalizado, subclassificado, objeto inválido, mock autorizado, conflito de seller e preservação da guarda Pix M40740. CI geral deve ser confirmada antes de outra sincronização source-only do Termux.

**Não executar no Debian ou Termux agora:** nenhum comando de migração, reinício, escrita de banco ou troca de credenciais. PostgreSQL FR Finance original `frcaixinha_aistudio_dev:5433` e FR Caixinha 2.2 preservados.

`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`; PR #2 permanece Draft. Reversão de mock-only exige revisão de segurança independente e aprovação explícita, nunca apenas variável de ambiente.
