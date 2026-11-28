# FR Finance M40760 — HTTP GET Mercado Pago somente por mock (NO-GO)

**Base:** M40750 `4301420`. Pacote restrito a código-fonte e testes offline, sem deploy e sem tocar a base original.

## Achado

O gateway `backend/app/mp_readonly_gateway.py` recebia qualquer `httpx.AsyncBaseTransport`. Um chamador do Python poderia fornecer `httpx.AsyncHTTPTransport`, ou um transporte customizado capaz de fazer rede ao provedor, apesar de o protótipo se declarar sandbox-only. Não é demonstração de endpoint HTTP público explorável. A verificação de seller através de `seller_authorization_checked=True` também não é prova independente de posse ou vínculo.

## Correção local ao adaptador

Agora `preview_sandbox_provider_get` exige `type(transport) is httpx.MockTransport` antes de construir o cliente HTTP. São negados `None`, `AsyncHTTPTransport`, qualquer transporte customizado e subclasses. O parser e suas salvaguardas continuam inalterados; os testes com mock mantêm respostas não financeiras, sem creditar valores nem contabilizar liquidação.

É uma trava de defesa em profundidade em um módulo. Não certifica todas as saídas HTTP possíveis do monorepo. Um callback Python passado ao mock ainda pode ter seus próprios efeitos colaterais; por isso os testes usam somente callbacks locais triviais. Tráfego real futuro exige revisão de arquitetura, credenciais de staging segregadas, HTTPS comprovado e aceite expresso.

## Continuam pendentes

- **M40730:** login SQL do emissor equivale a autorização de emissão de ticket, apesar de Ed25519 (**NO-GO**).
- **M40570 GUC:** `app.current_*` não é identidade não falsificável sob SQL arbitrário na role app (**NO-GO**).
- **M40740:** adaptador Pix mock-only; **M40750:** OAuth mock-only; **M40760:** leitura mock-only. Não implica que toda a infraestrutura está isolada.
- Faltam Vault/KMS, runtime owner atestado, controle de segredos, staging/TLS homologado e testes completos de integração.

`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`; PR #2 Draft.

Não há alteração do PostgreSQL `frcaixinha_aistudio_dev:5433`, outras bases, migrações, FastAPI em execução, serviços, Termux ou Debian. Não executar sincronização até CI geral 7/7 e teste M40760 específico aprovados.
