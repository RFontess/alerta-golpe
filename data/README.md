# Data card

Base de mensagens de SMS, WhatsApp e e-mail rotuladas como `golpe` ou `legitima`,
usada para treinar e avaliar o Alerta Golpe.

Leia a seção [Limitações](#limitações) antes de usar qualquer número daqui: a base é
pequena, é balanceada de propósito e as duas classes vêm de origens diferentes.

## Esquema

`data/raw/mensagens.csv`:

| coluna | o que é |
| --- | --- |
| `id` | identificador sequencial |
| `texto` | mensagem **já anonimizada** |
| `rotulo` | `golpe` ou `legitima` |
| `categoria` | tipo do golpe, ou `legitima` |
| `grupo` | modelo da mensagem; variações do mesmo modelo compartilham o grupo |
| `origem` | `real` ou `sintetica` |
| `fonte` | URL pública, `e-mail próprio` ou `exemplo sintetico, escrito para o projeto` |
| `data_coleta` | quando entrou na base |

A coluna `grupo` existe porque muitas variações só mudam o link ou o valor: 20
mensagens do Auxílio Brasil são **um** modelo, não 20 exemplos independentes. A
divisão entre treino e teste respeita o grupo, senão a métrica mediria memorização.

## Contagem

No repositório (`data/raw/mensagens.csv`), 99 mensagens:

| rótulo | origem | mensagens | grupos |
| --- | --- | --- | --- |
| golpe | real | 17 | 14 |
| legitima | real | 42 | 29 |
| legitima | sintetica | 40 | 19 |

Com os datasets externos baixados, `load_messages()` entrega 139 mensagens:

| rótulo | origem | mensagens | grupos |
| --- | --- | --- | --- |
| golpe | real | 57 | 26 |
| legitima | real | 42 | 29 |
| legitima | sintetica | 40 | 19 |

Os datasets externos trazem 51 golpes, mas 11 somem na remoção de duplicadas: as 20
variações do Auxílio Brasil só diferiam no endereço, e com `<LINK>` no lugar dele
viram o mesmo texto. É o efeito esperado, e mostra por que a contagem que importa é
a de grupos.

Por categoria, entre os 57 golpes: phishing 26, anúncio falso 14, Pix 9, boleto
falso 3, engenharia social 2, WhatsApp 2, falsa central 1.

O teste usa só `origem = real`: 57 golpes em 26 grupos contra 42 legítimas em 29.

## Fontes, por rótulo

| rótulo | fonte | mensagens |
| --- | --- | --- |
| golpe | datasets FraudTelegram.Br e FraudWhatsApp.Br | 40 |
| golpe | boatos.org (checagem, texto do print) | 15 |
| golpe | sosgolpe.com.br | 2 |
| legitima | e-mail próprio do autor, anonimizado | 42 |
| legitima | exemplo sintético escrito para o projeto | 40 |

Os golpes dos datasets vêm de **grupos públicos de Telegram e WhatsApp**; os de
checagem são o texto exato publicado no print da reportagem, com a URL na coluna
`fonte`. As legítimas reais são notificações automáticas recebidas pelo autor.

### Datasets externos

Os datasets são de Filho, J. M. M. et al., *FraudTelegram.Br e FraudWhatsApp.Br:
datasets de fraude em aplicativos de mensageria instantânea*, SBSeg 2023
(<https://github.com/jmmfilho/sec-fraudimabr>).

O repositório **não declara licença**, então o texto deles não está versionado aqui.
`python -m alerta_golpe.sources` baixa de um commit fixo para `data/external/`, que
está no `.gitignore`, e aplica a regra de seleção. O mesmo download roda no deploy.
O dataset GolpeBR foi avaliado e **descartado**, também por não ter licença.

Da classe de fraude desses datasets, só entra **golpe financeiro dirigido a uma
pessoa**. Ficou fora o que é outro gênero: propaganda de bot, spam de investimento
em cripto, venda de diploma e de gabarito, pirataria de TV e conteúdo político.

## Critério de rotulagem

- `golpe`: a mensagem tenta obter dinheiro ou dado da pessoa se passando por quem
  não é, ou oferecendo vantagem que não existe. Para os de checagem, o rótulo é o
  veredito publicado pelo checador, não a minha leitura.
- `legitima`: comunicação real de instituição com quem a pessoa tem relação, ou
  conversa comum do dia a dia.
- Mensagens de checagem cujo veredito era "o boato é sobre o golpe, não é golpe"
  foram descartadas, para não rotular errado.

## Anonimização

Tudo passa por `anonymize` antes de ser salvo. Marcadores: `<TELEFONE>`, `<EMAIL>`,
`<NOME>`, `<CPF>`, `<CNPJ>`, `<VALOR>`, `<LINK>`, `<CODIGO>`.

O texto dos golpes de checagem é guardado **anonimizado**, não como publicado: o
número pode ser de uma vítima de WhatsApp clonado e o link pode estar ativo. O texto
exato continua recuperável pela URL da coluna `fonte`.

Limites conhecidos da anonimização:

- A regra de nome só pega nome logo depois de saudação ou pronome de tratamento.
  Nome no meio da frase não é detectado.
- Tratamento genérico ("Prezado Cliente", "Oi Mãe") e nome de instituição ficam no
  texto de propósito: no lugar do nome da pessoa, são sinal de golpe.
- CPF sem pontuação tem onze dígitos, igual a celular com DDD, e sai como
  `<TELEFONE>`. O dado não vaza; o marcador é que fica errado.
- Depois de anonimizar, mensagens que só diferiam no código, no valor ou no
  endereço ficam idênticas e são removidas como duplicadas: 4 no CSV do
  repositório e 11 dos golpes externos.

## Sinais por rótulo

Proporção de mensagens que contêm cada sinal, sobre as 139:

| rótulo | n | `<LINK>` | `<VALOR>` | `<CODIGO>` | `<TELEFONE>` | instituição | tratamento genérico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| golpe | 57 | 63% | 49% | 9% | 2% | 32% | 12% |
| legitima | 82 | 17% | 12% | 11% | 0% | 9% | 6% |

## Adaptação de canal

Os e-mails legítimos chegaram **sem URL nenhuma**: 0 dos 45 originais tinham link no
corpo, porque o endereço estava atrás de botão HTML, que a exportação do texto
perdeu. Num SMS, o mesmo aviso traria o endereço escrito no meio da mensagem.

Para o teste não ficar com 0% de legítima com link, em **6 mensagens de 5 grupos**
onde o e-mail tinha botão clicável foi inserido `<LINK>` junto da chamada:

| grupo | chamada onde o marcador entrou |
| --- | --- |
| `oferta-de-credito-apos-mudanca-no-score-serasa` | "conferir suas possibilidades no Serasa Crédito?" |
| `compra-entregue-mercado-livre` | "devolver ou trocar grátis sua compra até 27 de setembro." |
| `pedido-enviado-com-rastreio-tiktok-shop` (2) | "Envio padrão: `<CODIGO>`" |
| `falha-no-pagamento-da-assinatura-chatgpt-plus` | "Atualizar pagamento" |
| `assinatura-pausada-por-falta-de-pagamento-claude` | "pague a fatura pendente." |

Só entrou onde havia botão de verdade. Ficaram **sem** marcador, de propósito, as que
parecem ter chamada mas não têm link: "conferir os detalhes no PDF anexo aqui no
e-mail" (Nubank, é anexo), "Simule na loja!" (Renner, é loja física), "analisar as
informações abaixo" (Microsoft, aponta para o corpo do e-mail) e a segunda entrega do
Mercado Livre, que só avisa que a compra chegou.

Nenhuma outra palavra foi acrescentada: o texto segue sendo o da mensagem recebida,
com o marcador posto onde o endereço estaria no SMS.

## Limitações

**A base é balanceada de propósito.** Na vida real, golpe é minoria do que chega no
celular. Como aqui as duas classes têm tamanho parecido, a **precisão medida no teste
é otimista**: em uso real, com muito mais mensagem legítima circulando, o mesmo
modelo produz proporcionalmente mais alarme falso. Recall de golpe é a métrica que
viaja melhor para o uso real.

**As duas classes vêm de origens diferentes, e isso contamina a comparação.** Os
golpes são SMS e mensagem de grupo; as legítimas reais são e-mail. O caso mais sério
é o link: 63% dos golpes têm URL escrita no meio da mensagem, contra 17% das
legítimas. O modelo pode aprender "link igual a golpe", que é atalho de formato e não
de conteúdo — e erraria numa notificação legítima de entrega, que no celular real vem
com link. A [adaptação de canal](#adaptação-de-canal) corrige parte disso e leva 6
legítimas **reais** com link para dentro do teste, mas a diferença entre as classes
continua grande. Na avaliação, medir também o desempenho **sem os sinais de canal**,
`<LINK>` incluído, para saber quanto o modelo depende deles.

**O que ficou fora do teste.** O teste usa só `origem = real`, então ficam fora:

- conversa pessoal do dia a dia (32 exemplos sintéticos), inclusive os casos
  difíceis de Pix entre amigos e cobrança informal entre conhecidos;
- as 8 legítimas sintéticas que já nasceram com link, criadas para o treino não
  depender do formato.

Marketing e oferta de crédito **estão** no teste: vieram reais (Serasa, Ticket,
Netshoes, Livelo, Renner, Pix no crédito do Nubank).

**Não há golpe recebido no e-mail do autor**, porque o conector usado não lê a pasta
de spam. Todo golpe da base é de fonte pública.

**Os golpes dos datasets são anúncio postado em grupo**, não mensagem recebida por
uma vítima. O gênero é parecido, mas não é o mesmo do caso de uso do app.

**A base é pequena**, e o número que limita não é a quantidade de mensagens, e sim a
de grupos: 26 modelos de golpe e 48 de legítima. Golpe novo, com texto diferente de
tudo isso, tende a passar.

**Nenhum dado pessoal real de terceiros.** As legítimas são do próprio autor, já sem
nome e sem e-mail antes de chegarem ao projeto, e passaram por revisão linha a linha.

## Como reproduzir

```bash
python -m alerta_golpe.sources   # baixa e filtra os golpes dos datasets externos
```

`data/raw/mensagens.csv` já vem no repositório.
