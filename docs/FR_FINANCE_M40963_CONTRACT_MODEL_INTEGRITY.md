# FR Finance — M40963 V2.2 contract model integrity manifest

## Escopo
- Publica somente SHA-256 e estado DRAFT_ONLY dos modelos genéricos A/B via GET público, sem autenticação, banco, identidade, nonce, assinatura ou side effect.
- A prévia Android/web compara os bytes locais com o digest fixado no backend, sem enviar o texto ao servidor; mismatch é sinalizado. Falha de rede mantém o rótulo de minuta e não declara integridade.
- Nenhum aceite, proposta de cobrança, convite, persistência, migração, escrita de banco, reinício ou operação real foi introduzido.
- SHA dos textos canônicos extraídos byte a byte do Caderno Mestre V2.2:
  - SAAS_LICENSE: `3d1a91d9674bd622da47d306f7517adc3aa87690c94c21838338c4c41eed18dc`
  - MEMBER_ADHESION: `8b4541f5c54702a33ee2172a7af369b480af00163e1f8605c2c9454b260bc6e8`

## Critérios/arquivos
- Backend `backend/app/routers/contract_models.py`; rota GET `/api/v1/public/contract-models/v2.2/{kind}`; manifesto estático `backend/app/contract_model_manifest_v22.json`.
- Montagem em `backend/app/main.py`; UI `src/components/ContractModelPreviewV22.tsx`; verificação cliente `src/services/contractModelIntegrityV22.ts`.
- Testes positivos/negativos/sem rede: `backend/tests/test_m40963_contract_model_manifest_ci.py`, `src/tests/m40963_contract_model_integrity_ci.test.ts`.
- Nenhum endpoint de escrita. PR #2 permanece Draft. Produção continua bloqueada e flags reais OFF.
