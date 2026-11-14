# FR Finance M37436 — auditoria do ciclo legada NO MESMO banco

M37435 local: 13 testes PASS, 1 politica antiga, 1 cota, 12 contribuicoes, 1 auditoria imutavel. Entre cinco constraints FK apontando para essas tabelas, uma referencia ao preco antigo foi verificada: a auditoria antiga depende da politica. Na tabela de auditoria ha dois triggers append-only: nao alterar nem apagar.

Este M37436 complementa o inventario com todos os relacionamentos por chave estrangeira de entrada para public.cycles, verifica que o ciclo antigo e o ciclo ABERTO de 2027, e faz contagens agregadas por tenant (sem imprimir identificadores de contas). Os resultados distinguem politica, cotas, contribuicoes, auditorias e FKs diretas para o ciclo. O inventario pode conter relacoes fora de FKs (metadata, event logs); ausencia de FK nao significa liberacao para exclusao.

Regra: mesmo projeto, branch, diretorio, PostgreSQL 18 127.0.0.1:5433/frcaixinha_aistudio_dev. Nao criar novo banco. O resultado nao executa migracao nem autoriza exclusao de auditoria. Futuro saneamento transacional deve preservar backup cifrado ja restaurado com sucesso, autorizacao explicita e testes CI em ambiente descartavel; habilitacao de Pix e usuarios reais segue OFF.
