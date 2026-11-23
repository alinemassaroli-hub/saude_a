# Instalação e operação da importação

## Arquitetura

O GitHub hospeda os lotes de contribuição e executa a validação mecânica em pull
requests e alterações de `main`. A ponte roda no computador responsável, lê apenas
JSON da branch `main`, valida com o código local e usa o consolidador do banco
existente. Ela não baixa nem executa scripts do repositório remoto.

O fluxo é: lote aceito em `main` → ponte local → pasta `entradas` do iCloud →
consolidador existente → registro transacional, exportações e recibo conferido.

A consulta ao repositório público não precisa de token. Nenhuma informação do
banco local é enviada ao GitHub. O código confere o SHA de cada arquivo baixado.
Configuração, cache, logs e recibos da ponte ficam em `.local/`, excluída do Git.

## Configurar no computador responsável

Antes de ativar, o banco deve estar instalado, com a configuração `banco-local.json`
funcionando. Ela informa os caminhos absolutos do banco, do iCloud, do Python e da
operação de consolidação. Cada computador mantém seus próprios caminhos.

Na raiz do projeto, usando o Python configurado no banco:

```sh
python3 -B scripts/configurar_importacao.py --config-banco /caminho/para/banco-local.json
python3 -B scripts/sincronizar_github.py --config .local/github.json --verificar
```

O segundo comando consulta e valida os lotes sem escrever no banco nem no iCloud.
Somente após verificar o destino, execute uma importação:

```sh
python3 -B scripts/sincronizar_github.py --config .local/github.json
```

## Ativar no macOS

```sh
python3 -B scripts/configurar_importacao.py --config-banco /caminho/para/banco-local.json --ativar
```

O instalador verifica a conexão e os lotes antes de ativar o LaunchAgent
`br.saudea.github`. O arquivo do agente permanece em `.local/` neste projeto.
Mantenha a pasta no mesmo lugar enquanto a rotina estiver ativa. A primeira
consulta ocorre na ativação; as seguintes, a cada 3600 segundos. O usuário precisa
estar conectado ao macOS e o computador disponível. Indisponibilidade de rede,
repouso ou limite da API adiam a importação para a próxima execução.

Para consultar e desativar:

```sh
launchctl print "gui/$(id -u)/br.saudea.github"
launchctl bootout "gui/$(id -u)/br.saudea.github"
```

O bootstrap direto vale para a sessão de login atual. Para reativação após reiniciar
ou encerrar a sessão, registre o mesmo plist em `~/Library/LaunchAgents/` usando
uma instalação com permissão de escrita nessa pasta. A documentação não afirma
persistência entre sessões quando o agente estiver apenas em `.local/`.

Em Linux, agende o comando de importação em um serviço do sistema ou cron usando
caminhos absolutos. O importador utiliza `fcntl` e não oferece rotina nativa Windows.

## Confirmação e falhas

- Cada lote é copiado como `github_NOME.json` na entrada já configurada.
- O consolidador atual valida e registra as questões, preserva as versões anteriores
  e atualiza as exportações. A ponte aguarda o término do comando.
- A ponte exige recibo com exatamente os IDs esperados e confere o conteúdo de cada
  revisão no SQLite antes de marcar a importação como concluída.
- Reenvio idêntico não duplica o banco. Uma falha entre registro e confirmação é
  retomada na execução seguinte; lotes originais permanecem preservados.
- Uma revisão com `versao_base` desatualizada gera conflito. Corrija com base na
  versão atual; não apague o histórico ou o estado para forçar uma importação.
- Lotes importados são imutáveis. Alteração, exclusão ou renomeação no GitHub
  interrompe a ponte e exige conferência. Envie revisões em arquivos novos.
- A API pública tem limite de consultas; um erro de rede ou HTTP não confirma
  importação. O estado só avança após recibo e leitura persistida.

Consulte `.local/ultimo_resultado.json`, `.local/github.log` e
`.local/github-erros.log`. Os recibos detalhados continuam na pasta `recibos` do
banco/iCloud. O envio remoto do iCloud depende da sincronização do macOS.

## Revisão e proteção de main

Configure no GitHub uma regra para `main` que exija pull request, revisão da
responsável indicada em `CODEOWNERS` e o status “Estrutura, taxonomia e testes”.
`CODEOWNERS` sozinho solicita revisores, mas não impede merges. Essa proteção
precisa ser ativada nas configurações do repositório e deve ser conferida após a
primeira execução de Actions. Sem a regra, quem tem escrita pode alterar `main`
diretamente; a ponte interpreta o conteúdo presente em `main` como aceito.

Contribuidores externos usam forks e pull requests. Não é necessário conceder
acesso de escrita ao banco ou ao iCloud. A primeira execução de Actions de um
fork pode depender de liberação manual no GitHub.
