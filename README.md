# Relatórios — Laudos e Audiências

Programa local (Streamlit) que lê as planilhas de controle de **laudos** e de
**audiências**, aplica os filtros de empresa/período/status e devolve o texto
do relatório já formatado, pronto para copiar e colar.

## Como instalar (uma vez só)

1. Instale o Python 3.10+ (https://www.python.org/downloads/), marcando a opção
   "Add Python to PATH" durante a instalação.
2. Abra o terminal (PowerShell) nesta pasta e rode:

```bash
pip install -r requirements.txt
```

## Como rodar todo dia

No terminal, dentro desta pasta:

```bash
streamlit run app.py
```

Isso abre uma aba no navegador com o programa. Para fechar, feche a aba e
aperte `Ctrl+C` no terminal.

### Deixar acessível para outros computadores da rede (vários funcionários)

Por padrão o programa só responde no próprio computador (`localhost`). Para
que outras pessoas da empresa acessem pelo navegador delas, rode assim no
computador/servidor que vai ficar sempre ligado:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Descubra o IP desse computador na rede (`ipconfig` no Windows, procure por
"Endereço IPv4") e passe para os funcionários o endereço
`http://IP-DO-COMPUTADOR:8501` — cada um abre esse link no navegador dele.
Como é o mesmo programa rodando, todos usam o mesmo banco de dados (veja a
seção "Banco de dados" abaixo): quem editar um valor, todo mundo já vê.

## Login (o código é público, o acesso não é)

Como este repositório é público no GitHub, o programa pede usuário e senha
antes de mostrar qualquer tela. A senha **não fica no código nem no
GitHub** — cada pessoa que roda o programa configura a sua:

**Rodando no seu computador:**

1. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml`
   (mesma pasta, sem o `.example` no final).
2. Abra o arquivo copiado e troque `TROQUE_ESTA_SENHA` pela senha que quiser
   (pode ter vários usuários, um por linha).
3. Rode `streamlit run app.py` normalmente — agora ele vai pedir login.

O arquivo `secrets.toml` fica só na sua máquina (está no `.gitignore`),
nunca é enviado ao GitHub.

**Publicado no Streamlit Community Cloud** (ver seção abaixo): a senha vai no
painel "Secrets" do próprio Streamlit Cloud, no mesmo formato do
`secrets.toml.example` — também não aparece no GitHub.

## Como usar

1. Escolha, no menu à esquerda, se é **Relatório de Laudos** ou
   **Relatório de Audiências**.
2. Envie o arquivo `.xlsx` da planilha correspondente.
3. Escolha a empresa, o período (e o status, no caso de laudos).
4. Clique em **Gerar relatório**.
5. O texto pronto aparece na caixa — selecione tudo (`Ctrl+A` dentro da caixa,
   depois `Ctrl+C`) e cole no relatório final. Também dá para baixar como
   `.txt` pelo botão abaixo da caixa.
6. Logo abaixo tem o botão **⬇️ Baixar PDF** — gera o mesmo relatório já na
   folha personalizada da empresa (logo, faixa e rodapé), pronto para enviar.

## Relatório em PDF (folha personalizada)

O botão **Baixar PDF** usa a mesma folha timbrada que já é usada hoje: uma
para laudos (marca ELITE) e outra para audiências (marca EXIMIA), guardadas
em `assets/laudos_logo_0.jpeg` e `assets/audiencias_logo_0.jpeg`.

Para trocar a folha (outra logo, outro rodapé, outra marca), basta substituir
o arquivo de imagem correspondente por uma nova imagem no tamanho de uma
folha A4 (retrato) — não precisa mexer em código. O texto do relatório
(empresa, período, tabela, total) é desenhado por cima dessa imagem
automaticamente.

## Como editar os valores (tipos de laudo, empresas de audiência, CNPJs)

Vá em **Gerenciar valores**, na aba do topo. Lá dá para:

- Ver, editar e remover o valor de cada tipo de laudo (ex: AUTO = R$ 40,00).
- Adicionar um tipo de laudo novo.
- Ver, editar e remover o valor por audiência de cada empresa.
- Adicionar uma empresa nova de audiência.
- Ver, editar e remover o CNPJ de cada empresa (usado para preencher o
  campo automaticamente na hora de gerar o relatório).

Tudo isso é salvo direto no banco de dados (veja a seção seguinte) — não
precisa mexer em nenhum arquivo nem reiniciar o programa.

## Banco de dados (vários funcionários, um só lugar de verdade)

O programa guarda os tipos de laudo, empresas de audiência e CNPJs num
banco de dados local: `data/leitor_relatorio.sqlite3`.

**O que isso muda na prática:** o programa roda uma vez só (num computador
ou servidor da empresa, sempre ligado) e todo mundo acessa pelo navegador
apontando para o endereço desse computador na rede. Como todos usam o
mesmo processo e o mesmo arquivo de banco, quando uma pessoa cadastra ou
edita um valor em "Gerenciar valores", as outras já veem a mudança no
próprio navegador delas, sem precisar recarregar nada.

Isso é diferente de cada pessoa rodar `streamlit run app.py` no seu
próprio computador — nesse caso, cada uma teria seu próprio banco
(`data/`), separado das demais.

**Primeira vez que o programa roda nesta pasta:** se existir um
`config.json` de uma instalação anterior, o programa importa os dados dele
automaticamente para o banco e renomeia o arquivo para
`config.json.importado` (só acontece uma vez). Se não existir, o banco já
nasce com os 6 tipos de laudo padrão.

**Backup:** basta copiar o arquivo `data/leitor_relatorio.sqlite3` para
outro lugar de vez em quando. Ele não é enviado ao GitHub (está no
`.gitignore`, junto com as planilhas) — é dado de cada instalação, não
código.

## Regras aplicadas

**Laudos**
- Período: sempre do dia 21 de um mês ao dia 20 do mês seguinte (as duas
  pontas incluídas). Escolha o mês/ano do dia 21 inicial na tela.
- Filtra por empresa (coluna `EMPRESA` da planilha) e por status
  (`Solicitação` ou `Corrigido`, comparado com a coluna `ENTRADA DE LAUDO`).
- Cada linha do relatório mostra data, cliente, tipo de laudo e valor (vindo
  da tabela de valores); no final soma um total geral — no mesmo formato do
  relatório de exemplo fornecido.
- Se aparecer um tipo de laudo sem valor cadastrado, o programa avisa na tela
  e permite cadastrar o valor em "Gerenciar valores" sem perder o restante
  do relatório.

**Audiências**
- Período: quinzenal — dia 1 ao dia 15, ou dia 16 ao último dia do mês
  (você escolhe o mês/ano e a quinzena na tela).
- Filtra só por empresa (todo relatório de audiência é sempre solicitação).
- O valor por audiência **não vem da planilha** — é cadastrado por empresa
  em "Gerenciar valores", porque a planilha de agendamento não tem essa
  coluna.
- O relatório mostra: período, valor por audiência, quantidade de clientes
  no período, a lista de clientes e o total (quantidade × valor).
- Se a empresa ainda não tiver valor cadastrado, o programa avisa e oferece
  um cadastro rápido na própria tela.

**Cobrança de Pendências**
- Só a ELITE usa essa planilha de controle de pagamento (colunas `EMPRESA`,
  `TIPO DE COBRANÇA`, `VALOR` ou `VALOR FALTANTE`, e opcionalmente `PAGO`).
- Conta como pendente qualquer linha em que `PAGO` não seja exatamente
  `SIM` (cobre `NÃO`, `EM ATRASO`, `ACORDO`, `PENDENTE` e célula vazia —
  nesse último caso vale conferir antes de enviar).
- Cada linha pendente é classificada automaticamente por quem cobra: tipo
  de cobrança com "AUDIÊNCIA" no texto vai para a EXIMIA; qualquer outro
  tipo (LAUDOS, MENSALIDADE, etc.) vai para a ELITE. Se a empresa tiver
  pendência dos dois ao mesmo tempo, o programa gera duas mensagens
  separadas, uma para cada PIX.
- A descrição de cada pendência (o texto depois do "-" na mensagem) é
  copiada direto do `TIPO DE COBRANÇA` da planilha, só arrumando espaços
  extras — por isso mantém a redação de quem preencheu a planilha.

## Publicar no GitHub e deixar acessível pela internet

O repositório **não inclui planilhas, senha nem o banco de dados**
(`.gitignore` bloqueia `.xlsx`/`.csv`, `secrets.toml` e a pasta `data/`) —
só o código do programa.

**1. Enviar o código para o GitHub** (repositório vazio já criado no site):

```bash
git remote add origin https://github.com/SEU-USUARIO/NOME-DO-REPOSITORIO.git
git branch -M main
git push -u origin main
```

**2. Deixar rodando na internet (opcional)**, sem precisar deixar seu
computador ligado, usando o Streamlit Community Cloud (gratuito):

1. Acesse https://share.streamlit.io e entre com sua conta do GitHub.
2. Clique em "New app", escolha este repositório, arquivo principal `app.py`.
3. Em "Secrets" (configurações avançadas), cole o conteúdo de
   `.streamlit/secrets.toml.example` já com a senha real preenchida.
4. Clique em "Deploy". Em alguns minutos você recebe um link
   `https://seu-app.streamlit.app` para acessar de qualquer lugar — ele vai
   pedir o login configurado no passo 3 antes de mostrar as telas.

## Tipos de laudo vistos na planilha mas ainda sem valor cadastrado

Ao revisar a planilha inteira em 2026-09, encontrei estes nomes de tipo de
laudo que aparecem em algum registro mas não têm valor na tabela — enquanto
não forem cadastrados em **Gerenciar valores**, esses laudos entram no
relatório como R$ 0,00 (o programa avisa na tela quando isso acontece):

- AUTO (BALÃO)
- AUTO (REFIN)
- AUTO(CONSÓRCIO)
- BALÃO
- CONSIGNADO
- FINANCIAMENTO
- LOTE
- PLACA SOLAR
- REFIN

Alguns parecem variações de tipos já cadastrados (ex: `BALÃO` vs
`AUTO-BALÃO`, `LOTE` vs `LOTEAMENTO`) — vale conferir com quem preenche a
planilha se são o mesmo tipo (aí é só usar a grafia já cadastrada) ou tipos
realmente novos (aí é só adicionar o valor).

## Observações técnicas

- O programa lê automaticamente todas as abas de cada planilha que tenham as
  colunas esperadas (não é preciso indicar o nome da aba do mês) — abas de
  dashboard/controle sem essas colunas são ignoradas.
- Nomes de empresa, tipo de laudo e status são comparados ignorando
  maiúsculas/minúsculas, acentos e espaços extras.
