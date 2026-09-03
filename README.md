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

## Como editar os valores (tipos de laudo e empresas de audiência)

Vá em **Gerenciar valores**, no menu à esquerda. Lá dá para:

- Ver, editar e remover o valor de cada tipo de laudo (ex: AUTO = R$ 40,00).
- Adicionar um tipo de laudo novo.
- Ver, editar e remover a modalidade de contratação e o valor por audiência
  de cada empresa.
- Adicionar uma empresa nova de audiência.

Tudo isso é salvo automaticamente no arquivo `config.json`, nesta mesma
pasta — não precisa mexer em código. Se preferir editar esse arquivo
diretamente (por exemplo, para colar vários valores de uma vez), o formato é:

```json
{
  "laudos": {
    "AUTO": 40.0,
    "AUTO-BALÃO": 60.0
  },
  "audiencias": {
    "ANGITU": { "modalidade": "Avulso", "valor": 400.0 }
  }
}
```

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
- Modalidade de contratação e valor por audiência **não vêm da planilha** —
  são cadastrados por empresa em "Gerenciar valores", porque a planilha de
  agendamento não tem essas colunas.
- O relatório mostra: período, modalidade, valor por audiência, quantidade
  de clientes no período, a lista de clientes e o total (quantidade × valor).
- Se a empresa ainda não tiver modalidade/valor cadastrados, o programa avisa
  e oferece um cadastro rápido na própria tela.

## Publicar no GitHub e deixar acessível pela internet

O repositório **não inclui planilhas nem dados de cliente** (`.gitignore`
bloqueia `.xlsx`/`.csv` e o `secrets.toml` com a senha) — só o código e a
tabela de valores (`config.json`).

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
