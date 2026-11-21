# FR Finance AI Studio — Macropacote M25400: contrato canônico

## Implementação
- Nova rota autenticada `POST /api/v1/invitations/preflight/contract-content`.
- Seleção explícita de perfil, tenant e ID de documento, com RLS.
- Serviço `canonical_contract_store.py`: só entrega texto UTF-8 de um
  documento de adesão *publicado* no PostgreSQL se os bytes exatos
  corresponderem ao SHA-256 publicado. Falha com 503 se não houver arquivo,
  permissão segura ou integridade; não devolve caminhos internos.
- O arquivo **não é enviado por esta API**. Deploy autorizado deve
  provisionar um diretório absoluto `FR_FINANCE_CANONICAL_CONTRACT_DIR`,
  não editável pela aplicação, contendo arquivos `<uuid>.txt`
  imutáveis, propriedade e permissões revisadas pelo operador.
- Na interface Master/Administrador: botão "Carregar texto canônico verificado
  do servidor". O cliente valida novamente o SHA-256 via WebCrypto, conferindo
  documento e hash retornados com o catálogo consultado.
- O texto não é persistido no navegador, não há assinatura, envio de convite,
  aceite nem criação de usuário. O botão não substitui a confirmação
  explícita por parte da própria identidade convidada.

## Riscos e limitações

Os arquivos devem ser distribuídos por mecanismo seguro de implantação com
proveniência revisada. O envio de texto/UTF-8 serve apenas para documentos
textuais; não confere bytes de PDF. HTTPs real, versão aprovada do contrato,
aceite explícito por pessoa convidada, CPF validado, e-mail confirmado,
segregação de funções e auditoria transacional permanecem essenciais.
Não se deve habilitar escrita em banco nem Pix real por causa desse pacote.

## Testes

`test_m25400_canonical_contract_delivery_ci.py` exercita integridade, UTF-8,
versão não publicada, tenant, permissões e caminho de arquivo.
`m25400_canonical_contract_ui_ci.test.ts` verifica hash no cliente e
conserva o bloqueio de assinatura e cadastro. A CI executa ambos.

## Exemplo de provisionamento manual, sem alterar a base

```bash
# O operador deve obter arquivo e SHA de uma versão jurídica aprovada,
# depois criar diretório seguro fora do repositório.
# NÃO use contrato fictício nem credenciais neste material.
# Cada arquivo: UUID-do-documento.txt, UTF-8, hash igual ao SQL publicado.
# Permissões esperadas pelo serviço: diretório sem escrita por group/other,
# arquivo sem escrita por owner/group/other.
```

## Distinguir estados

- **Implementado**: verificação e leitura de arquivo com SHA/ACLs e RLS.
- **Não implantado no Termux**: volume de documentos canônicos aprovado.
- **Não ativado**: assinatura/aceite/convite/recuperação real de senha.
- **Não implantado**: OCI TLS, provider real de e-mail e Pix.
