# Saúde A — elaboração colaborativa de questões

Espaço público para elaborar, revisar e encaminhar questões originais de Enfermagem
ao banco da Saúde A. Coordenação editorial: Aline Massaroli.

**Comece por [Como contribuir](CONTRIBUTING.md).** Você pode preparar o conteúdo com
o [roteiro de elaboração](docs/ROTEIRO_DE_ELABORACAO.md), usar o modelo JSON e enviar
um pull request (proposta de inclusão). Não é necessário receber permissão de escrita
para contribuir: use um fork, a sua cópia do repositório.

## Fluxo de trabalho

1. Elabore o lote conforme a taxonomia e os critérios editoriais.
2. Envie o JSON em `entradas/` por pull request para `main`.
3. O GitHub Actions confere a estrutura, os códigos, o gabarito, as referências
   obrigatórias e a extensão das explicações.
4. A responsável revisa o conteúdo e aceita a contribuição em `main`.
5. A ponte instalada no computador responsável busca os lotes aceitos, encaminha-os
   à rotina existente e confirma IDs, versões e conteúdo persistido por recibo.
6. O consolidador do banco atualiza SQLite, JSON e a planilha `banco_questoes.xlsx`.

**A importação depende de a ponte local estar configurada e ativa.** A rotina
consulta o GitHub ao iniciar e a cada hora enquanto o computador está disponível.
GitHub Actions valida as contribuições; ele não acessa o iCloud nem o banco local.
Veja [Instalação e operação](docs/IMPORTACAO.md).

## Início rápido

Requer Python 3.12 ou posterior, sem pacotes adicionais:

```sh
python3 -B scripts/novo_lote.py --subcategoria 10.04 --autor "Seu nome" --quantidade 5
python3 -B scripts/validar_lotes.py entradas
python3 -B -m unittest discover -s tests -v
```

O primeiro comando cria um rascunho com campos em branco. Preencha todos os itens e
defina o gabarito antes da validação. Os códigos e nomes de **12 categorias e 96
subcategorias** estão em [taxonomia.json](references/taxonomia.json).

## Conteúdo e responsabilidades

- Cinco alternativas por questão; resposta única como padrão.
- IDs permanentes; gabarito vinculado ao ID e ao texto, compatível com embaralhamento.
- Explicações de 750–1000 palavras, com discussão integrada de todas as opções.
- Referências verificadas, com localização e data de acesso.
- Dificuldade estimada, objetivo de aprendizagem e status editorial explícitos.

A validação mecânica não comprova correção científica, vigência normativa ou
qualidade pedagógica. A revisão especializada deve ocorrer antes da publicação
para estudantes. Importar ao banco não equivale a publicar na plataforma.

Este repositório publica as contribuições enviadas para colaboração. O banco
preexistente, backups, configurações locais e dados de acesso não integram o
projeto. Utilize casos fictícios; nunca envie dados identificáveis de pacientes.

## Organização

| Caminho | Finalidade |
| --- | --- |
| `entradas/` | Lotes enviados para revisão e aceitos em `main` |
| `modelos/lote-modelo.json` | Rascunho preenchível; não deve ser importado sem completar |
| `scripts/novo_lote.py` | Gerar IDs e preencher a classificação |
| `scripts/validar_lotes.py` | Conferir lotes sem alterar o banco |
| `scripts/sincronizar_github.py` | Buscar lotes de `main` e confirmar a importação |
| `scripts/configurar_importacao.py` | Preparar e ativar a ponte local no macOS |
| `docs/` | Orientações para autores, revisores e manutenção |
| `.github/workflows/validar.yml` | Validação no GitHub |

## Revisões de questões existentes

Mantenha o ID da questão e os IDs das opções. Inclua `versao_base` com a versão atual
do banco e envie **outro arquivo de lote**. Reenvios idênticos não duplicam o registro;
alterações com versão desatualizada são rejeitadas. Lotes já importados são imutáveis.

## Direitos de uso

O acesso público não concede, por si só, uma licença ampla de uso comercial.
Contribua apenas com conteúdo original ou cujo uso você possa autorizar.
Ao enviar um lote, autorize expressamente sua avaliação e incorporação à Saúde A
no formulário do pull request. Uma política de licenciamento mais ampla poderá
ser definida pela responsável pelo projeto.

