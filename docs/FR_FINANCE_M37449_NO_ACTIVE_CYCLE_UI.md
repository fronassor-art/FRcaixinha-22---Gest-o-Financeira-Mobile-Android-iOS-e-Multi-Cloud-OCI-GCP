# FR Finance M37449 — interface após o saneamento do ciclo antigo

O M37448 comprova FastAPI local ON, sessões autenticadas de homologação
e o M37443 confirmou zero ciclos e contribuições no banco original.
Mesmo assim o painel ADMIN mostrava aviso de ciclo não homologado.

Origem: a função GET de política ativa retorna HTTP 404 quando não há
ciclo aberto; o frontend mapeava qualquer erro para a mensagem de
política irregular. M37449 trata apenas o HTTP 404 desse endpoint como
estado informativo. Erros 401/403 (sessão), 409 (legado), 503/5xx
(indisponibilidade) e falhas de formato permanecem alertas.

O botão Atualizar passa a atualizar também a consulta da política.
A prévia administrativa segue disponível sem criar ciclo, sem preço
default e sem liberar Pix. O aviso de licença não confirmada na área
Master depende de licenciamento real: não será forjado pela UI.

Sem SQL, sem migrações, sem nova base, sem habilitar Pix.
O APK M37447 instalado só refletirá o ajuste após nova compilação.