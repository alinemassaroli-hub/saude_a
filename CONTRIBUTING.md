# Como contribuir

## 1. Escolha a classificação

Consulte `references/taxonomia.json`. Escolha uma subcategoria principal pelo
conhecimento exigido no comando da questão. Leia o escopo e as exclusões. Preserve
os nomes e códigos, inclusive zeros à esquerda. Não crie categorias novas.

## 2. Prepare o lote

**Com Python:** baixe o projeto ou faça um fork e execute:

```sh
python3 -B scripts/novo_lote.py --subcategoria 10.04 --autor "Seu nome" --quantidade 5
```

O código `10.04` corresponde a Trauma e queimaduras. Ajuste-o conforme seu tema.
O arquivo será criado em `entradas/` com data/hora UTC e identificador aleatório.

**Pelo navegador:** faça um fork, copie `modelos/lote-modelo.json` e crie um arquivo
em `entradas/` usando **Add file → Create new file**. Complete os campos e substitua
os UUIDs de exemplo por UUIDs próprios. A geração por Python é recomendada para
evitar colisões de identificadores.

Preencha os metadados e as cinco opções. O rascunho aponta inicialmente para a
primeira opção: **ajuste o ID e o texto do gabarito para a resposta realmente correta**.
As alternativas são objetos completos, que devem ser movidos juntos ao embaralhar.

Use o roteiro em `docs/ROTEIRO_DE_ELABORACAO.md`. A explicação tem de 750 a 1000
palavras, excluindo referências, dica, enunciado, gabarito e metadados. Referências
devem informar `citacao`, `url`, `localizacao` e `data_acesso` em AAAA-MM-DD.

## 3. Confira

```sh
python3 -B scripts/validar_lotes.py entradas
```

O resultado deve ser `checagem_mecanica: aprovada`. Uma pasta vazia é aceita para
inicialização do projeto; um arquivo de lote com lista vazia é rejeitado.
O rascunho em `modelos/` contém campos em branco e não participa da importação.

## 4. Envie um pull request

No seu fork, salve o arquivo e abra **Contribute → Open pull request**, com destino
`alinemassaroli-hub/saude_a`, branch `main`. Informe tema, quantidade, autoria,
fontes conferidas e pendências. Preencha a lista de revisão apresentada pelo GitHub.
Contribuições externas podem precisar de liberação da primeira execução de Actions.

Aguarde a validação e a revisão da responsável. Se forem solicitados ajustes, edite
o mesmo arquivo enquanto o lote ainda não foi importado. Depois do aceite e da
importação, qualquer mudança precisa de um novo lote de revisão.

## 5. Acompanhe a importação

O aceite em `main` torna o lote elegível à importação horária no computador
responsável. Somente o recibo local confirma a gravação. Um teste verde no GitHub
confirma estrutura; não confirma gravação no banco nem publicação para estudantes.

## Revisar um item já existente

Solicite à coordenação a versão atual. Preserve os IDs, inclua `versao_base` e gere
novo `lote_id` e arquivo com data/hora posterior. Não altere ou apague lotes aceitos.
Se houver conflito, releia a versão atual antes de reenviar. A integração não
sobrescreve silenciosamente o histórico do banco.

## Limites do arquivo

Use um objeto JSON por arquivo, até 2 MB e de 1 a 100 questões. Nomeie o arquivo
com data/hora UTC seguida de identificador, por exemplo:
`20261123T210000Z_1f8ac0935e42.json`. Preserve a ordem cronológica dos lotes;
ela determina o processamento de revisões. Não envie documentos privados, planilhas
com o banco completo, senhas, chaves ou dados de pacientes.

