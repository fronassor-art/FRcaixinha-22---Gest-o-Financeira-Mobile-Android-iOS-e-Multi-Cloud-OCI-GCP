# M23000 — Callback OAuth público desde o início da conexão

M22700 já rejeitava determinados URLs inadequados no momento da troca de token. M23000 antecipa a rejeição para a criação do estado OAuth/PKCE, reduzindo tentativas impossíveis e evitando callbacks acidentais apontando para Termux, VMs privadas ou IPs.

Exige HTTPS, hostname DNS completo sem usuário/senha/porta, sem fragmento/query, caminho explícito e sem sufixos privados (localhost, .local, .internal). Conserva a URL do teste sintético app.example.invalid; isso não é um endereço de implantação real nem libera envio de usuários a ele.

O cliente só pode ser vinculado após a infraestrutura OCI, domínio real e callback registrado no Mercado Pago, state/PKCE com consumo atômico no banco e tokens protegidos no Vault. M23000 não configura callback, não troca token, não cria webhook nem faz operação financeira.
