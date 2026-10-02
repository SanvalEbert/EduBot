# Como o rastreio do EduBot funciona — a tecnologia por trás

> **Pergunta**: na prática, com que tecnologia o EduBot mede o que o aluno faz?
>
> **Para quem**: quem precisa *explicar* o sistema — em banca, em reunião, num
> artigo — sem ter escrito o código. Assume que você sabe o que é um site e uma
> requisição HTTP; não assume mais nada.
>
> **Resumo em uma frase**: o rastreio é um **programa em JavaScript que roda no
> navegador do aluno**, observa o que acontece na tela através de sensores que o
> próprio navegador oferece, e a cada 15 segundos envia um resumo por **HTTP,
> carimbado com um token de identidade**, para uma **API em Python** que soma
> esses números dentro do **MySQL**.
>
> Documento vizinho: [ARQUITETURA_EDUBOT.md](ARQUITETURA_EDUBOT.md) (o sistema
> inteiro; os eventos estão no §4.2).

---

## 1. O desenho mínimo

Três peças, e nada mais:

```
   NAVEGADOR DO ALUNO                SERVIDOR                    BANCO
┌─────────────────────┐      ┌────────────────────┐      ┌──────────────┐
│  JavaScript (React) │      │  Python (Flask)    │      │  MySQL 8.4   │
│                     │      │                    │      │              │
│  sensores ──────────┼─────▶│  confere o token   │─────▶│  soma o      │
│  acumulam números   │ HTTP │  identifica o aluno│ SQL  │  número na   │
│  a cada 1 segundo   │ JSON │  valida o dado     │      │  linha dele  │
│                     │      │                    │      │              │
│  envia a cada 15 s  │      │  @require_auth     │      │  UPDATE      │
└─────────────────────┘      └────────────────────┘      └──────────────┘
```

Uma frase por peça:

- **O navegador mede.** Ele é o único lugar que sabe se a aba está visível, se o
  mouse mexeu, se o vídeo está tocando, se a seção está na tela.
- **O servidor decide se acredita.** Ele confere quem está falando e recusa
  qualquer dado que não venha com identidade válida.
- **O banco acumula.** Ele é a única fonte de verdade — nada de rastreamento fica
  guardado no navegador.

---

## 2. A primeira coisa a entender: o crachá

Antes de medir qualquer coisa, o sistema precisa saber **de quem** é aquele
segundo de leitura. É aqui que entra o **token**.

### O que é o token, concretamente

Quando o aluno faz login, o servidor devolve uma string com duas partes separadas
por um ponto:

```
eyJzaWQiOiA0MiwgImV4cCI6IDE3NTgyMzQ1Njd9.a3f9c2e1b8...
└──────────── parte 1 ────────────────┘ └── parte 2 ──┘
     os dados, em base64                   a assinatura
```

- **Parte 1** são os dados, legíveis por qualquer um: o número do aluno (`sid`) e
  a data de expiração (`exp`, sete dias à frente). Não é segredo — é só
  codificação, não criptografia.
- **Parte 2** é a **assinatura HMAC-SHA256**: o servidor passou a parte 1 por uma
  função matemática junto com uma chave secreta que só ele conhece.

A propriedade que faz isso funcionar: **qualquer pessoa pode ler a parte 1, mas
ninguém consegue produzir a parte 2 sem a chave secreta.** Se um aluno editar o
token para dizer `"sid": 43` e tentar se passar por outro, a assinatura não bate
mais e o servidor recusa.

> **Detalhe de segurança real no código**: a comparação da assinatura usa
> `hmac.compare_digest` em vez de `==`. Um `==` comum para de comparar no primeiro
> caractere diferente, e o tempo dessa comparação vaza informação suficiente para
> um atacante adivinhar a assinatura byte a byte. `compare_digest` sempre leva o
> mesmo tempo.

Não é JWT — é um formato próprio de três linhas, feito só com a biblioteca padrão
do Python, sem dependência externa.

### Como o token viaja

Toda requisição de rastreio leva um cabeçalho HTTP:

```
Authorization: Bearer eyJzaWQiOiA0Mi...a3f9c2e1b8
Content-Type: application/json
```

No servidor, um **decorador** do Flask chamado `@require_auth` intercepta a
requisição antes de a rota rodar: ele lê o cabeçalho, confere a assinatura, busca
o aluno no banco e o deixa disponível em `g.student`.

**Essa é a regra de ouro do sistema inteiro:** o aluno é sempre resolvido *do
token*, **nunca lido do corpo da requisição**. Mesmo que alguém envie
`{"student_id": 7}` no JSON, o servidor ignora — ele usa `g.student`. É o que
impede um aluno de gravar progresso na conta de outro.

---

## 3. Os cinco sensores do navegador

O JavaScript não "adivinha" nada: ele usa APIs que o próprio navegador
disponibiliza. São cinco, e cada uma responde a uma pergunta diferente.

### Sensor 1 — O cronômetro: `setInterval`

```js
window.setInterval(() => { /* ... */ }, 1000);
```

Roda uma função uma vez por segundo. É o coração do rastreio de tempo. Mas ele
**não** conta o segundo automaticamente — antes de contar, consulta os sensores 2
e 3.

### Sensor 2 — O olho: Page Visibility API

```js
document.visibilityState === "hidden"
```

O navegador informa se a aba está realmente à vista. Se o aluno trocou de aba,
minimizou a janela ou abriu outro programa por cima, isso vira `"hidden"` e o
segundo é descartado. **É o que impede "deixar a aba aberta" de virar tempo de
estudo.**

### Sensor 3 — A presença: escuta de eventos de interação

```js
["mousemove", "keydown", "pointerdown"].forEach(ev =>
  window.addEventListener(ev, markActivity, { passive: true }));
window.addEventListener("scroll", onScroll, { passive: true });
```

Cada vez que o aluno mexe o mouse, digita, toca a tela ou rola a página, o código
anota o horário. Se passarem **180 segundos** sem nenhum desses sinais, o
cronômetro entende que o aluno saiu da frente do computador, para de contar e
registra um evento `idle_start`. Quando ele volta, registra `idle_end` com quanto
tempo ficou ausente.

> `{ passive: true }` avisa ao navegador que a função não vai bloquear a rolagem.
> Sem isso, escutar `scroll` deixa a página perceptivelmente travada.

### Sensor 4 — A posição na página: `IntersectionObserver`

Essa é a API que responde **"qual parte do texto está na tela agora?"**.

```js
new IntersectionObserver(callback, { threshold: 0.5 });
```

Em vez de o programa ficar perguntando "onde está a seção 3?" mil vezes por
segundo — o que travaria a página —, ele **registra um aviso**: "me chame quando
metade da seção 3 entrar ou sair da tela". O navegador faz esse cálculo por
conta própria, de forma otimizada, e só chama o código quando a situação muda.

O `threshold: 0.5` é o "metade". E há uma segunda regra, essa escrita no código do
EduBot: a seção precisa ficar visível por **pelo menos 1 segundo** para contar
como lida — rolagem rápida atravessando a tela não é leitura.

### Sensor 5 — Os players de mídia

Aqui são duas tecnologias diferentes, porque há dois tipos de vídeo:

**Vídeo próprio (HTML5)** — o elemento `<video>` do HTML já emite eventos
prontos, e o código só precisa escutá-los:

```js
video.addEventListener("play",       onPlay);
video.addEventListener("pause",      onPause);
video.addEventListener("ended",      onEnded);
video.addEventListener("ratechange", () => onRate(video.playbackRate));
video.addEventListener("timeupdate", () => positionRef.current = video.currentTime);
video.addEventListener("seeking",    () => seekFrom = positionRef.current);
video.addEventListener("seeked",     () => /* compara origem e destino */);
```

**YouTube** — o player está dentro de um iframe do YouTube, e o navegador
**proíbe** ler o conteúdo de um iframe de outro domínio. A solução é a
**YouTube IFrame Player API**: o código carrega dinamicamente um script do
YouTube (`https://www.youtube.com/iframe_api`) que cria um canal de comunicação
oficial com aquele player. Como essa API não oferece um evento contínuo de
posição, o EduBot **consulta a posição uma vez por segundo**.

> Por que `seeking` **e** `seeked`: na maioria dos navegadores o `seeking` dispara
> *antes* de a posição saltar. O código guarda a posição de origem no `seeking` e
> só compara com o destino no `seeked` — é assim que se sabe *de onde para onde*
> o aluno arrastou a barra.

---

## 4. O carteiro: `fetch` com token e `keepalive`

Medir não adianta se o dado não chegar. O envio usa a API `fetch` do navegador:

```js
fetch(BASE_URL + path, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  },
  keepalive: options.keepalive,
  body: JSON.stringify(data)
});
```

Três detalhes que importam:

**`keepalive: true`** é o que permite que um POST **sobreviva ao fechamento da
aba**. Normalmente, quando o aluno fecha a página, o navegador cancela as
requisições pendentes — e os últimos segundos de leitura se perderiam. Com
`keepalive`, o navegador se compromete a terminar o envio mesmo com o documento
já sendo destruído.

**Por que não `navigator.sendBeacon`** — que é a API "clássica" para isso? Porque
o `sendBeacon` **não permite definir cabeçalhos**, e sem o cabeçalho
`Authorization` o servidor não saberia de quem é o dado. Como o EduBot resolve o
aluno pelo token, o `fetch` com `keepalive` é a única opção que funciona.

**O gatilho é `pagehide`, não `unload`.** O evento `pagehide` cobre mais casos
(fechar a aba, navegar para fora, o navegador descarregar a página em segundo
plano no celular) e é o recomendado atualmente.

---

## 5. Um segundo de leitura, do olho ao disco

Agora juntando tudo. O aluno está lendo um OVA há 3 minutos.

**No navegador, a cada segundo:**

1. O `setInterval` dispara.
2. Pergunta ao **sensor 2**: a aba está visível? Se não → descarta o segundo, fim.
3. Pergunta ao **sensor 3**: houve interação nos últimos 180 s? Se não → registra
   `idle_start`, descarta o segundo, fim.
4. Passou nos dois portões: soma `+1` em dois contadores na memória —
   `unsyncedRef` (o que ainda não foi enviado) e `sessionSecondsRef` (o total da
   sessão).
5. Chama `creditSecond()`, que pergunta ao **sensor 4** quais seções estão na tela
   e credita aquele mesmo segundo a elas. Se duas seções estiverem visíveis ao
   mesmo tempo, o segundo é **dividido** entre as duas — senão a soma das partes
   ficaria maior que o todo.

**No navegador, a cada 15 segundos** (ou quando a aba é escondida, ou no
`pagehide`):

6. O código pega o valor acumulado — digamos 15 — **zera o contador** e envia:

```http
POST /progress/ova
Authorization: Bearer eyJzaWQiOiA0Mi...
Content-Type: application/json

{"ova_id": 3, "seconds_delta": 15, "perc_scrolled": 47, "completed": false}
```

Repare que ele manda **15**, e não "estou em 195 segundos no total". Isso se chama
enviar o **delta** — a diferença desde o último envio.

**No servidor:**

7. O `@require_auth` confere a assinatura do token e descobre que é o aluno 42.
8. A rota valida os números e monta uma instrução SQL através do **Peewee**, que é
   o ORM (a biblioteca que traduz objetos Python em SQL):

```sql
UPDATE ova_progress
   SET read_time = COALESCE(read_time, 0) + 15,
       perc_scrolled = 47,
       last_access = NOW()
 WHERE student_id = 42 AND ova_id = 3;
```

**No banco:**

9. O MySQL executa a soma. E aqui está a parte mais sutil do sistema inteiro: **a
   soma acontece dentro do banco, não no Python.**

**Se der erro de rede** no passo 6, o código devolve os 15 segundos ao contador e
tenta de novo no ciclo seguinte. Só o envio final de saída abre mão disso — não
existe "próximo ciclo" depois que a aba fecha.

---

## 6. Por que o banco soma, e não o Python

Essa decisão parece um detalhe técnico e é, na verdade, o que torna a métrica
correta. Compare:

**Jeito ingênuo** (ler, somar em Python, gravar):

```
Aba A lê: read_time = 100        Aba B lê: read_time = 100
Aba A calcula: 100 + 15 = 115    Aba B calcula: 100 + 12 = 112
Aba A grava: 115                 Aba B grava: 112   ← apagou os 15 da aba A
```

**Jeito do EduBot** (mandar a instrução de somar para o banco):

```
Aba A manda: "some 15"           Aba B manda: "some 12"
O MySQL serializa as duas operações → resultado final: 127. Nada se perde.
```

O mesmo raciocínio vale para o `watched_seconds` do vídeo e o `active_seconds` de
cada seção. Já valores como `perc_scrolled` ou `coverage_perc` seguem outra
regra — **marca d'água**: só sobem, nunca descem. Se duas abas competirem, o pior
que acontece é a marca demorar um ciclo para subir, e o envio seguinte corrige.

---

## 7. O caso do vídeo: por que uma sequência de 100 zeros e uns

Medir vídeo é mais difícil que medir texto, porque o aluno pode **pular**. Se o
sistema só guardasse "a maior posição alcançada", arrastar a barra até o fim
marcaria 100% sem o aluno ver nada.

A solução é uma string de **100 caracteres**, um por 1% da duração do vídeo:

```
1111111111111111111111111111111111111111111110000000000000001111111111111111110000000000000000000000
└──── assistiu 0–45% ────────────────────────┘└─ pulou ────┘└── assistiu 60–78% ┘└── arrastou até o fim ┘
```

A regra que faz isso ser honesto é de uma linha só: **a função que acende um
balde só é chamada de dentro do cronômetro de reprodução.** O evento de "pular"
não acende balde nenhum. Como o cronômetro só roda quando o vídeo está tocando
*e* a aba está visível, cada `1` significa literalmente "esse pedaço passou pela
tela do aluno".

O navegador manda a sequência **inteira e acumulada** a cada 10 segundos
assistidos, e o servidor combina com a que já estava salva usando um **OU lógico**
(se qualquer um dos dois tem `1`, o resultado é `1`). Isso dá uma propriedade
valiosa: se um envio se perder na rede, o próximo reenvia tudo e a cobertura se
reconstrói sozinha.

> **Exceção deliberada**: o **podcast** não tem o portão de visibilidade. Ouvir em
> segundo plano é escuta legítima — quem escuta podcast não fica olhando para a
> tela. Ele mede tempo real de escuta, 1 segundo por segundo tocando.

---

## 8. O segundo canal: os eventos

Além dos números que se acumulam (segundos, porcentagens), o sistema registra
**acontecimentos**: entrou, pausou, pulou, respondeu, perguntou ao tutor. São os
**eventos de aprendizado**, num formato inspirado no padrão xAPI:

```json
{
  "verb": "section_enter",
  "object_type": "ova_section",
  "object_id": 3,
  "context": { "section_id": "bkt-intro", "session_id": "a3f9-..." },
  "occurred_at": "2026-09-18T13:42:07.512Z"
}
```

Quatro decisões de projeto explicam esse formato:

**O vocabulário é fechado.** Existem exatamente 20 verbos e 6 tipos de objeto
aceitos, definidos numa lista única no servidor. Um verbo fora da lista é
recusado. Parece burocracia, mas é o que permite perguntar "quantas vezes a turma
pausou vídeos esta semana" — com texto livre em português, como era antes, essa
pergunta não tem resposta.

**Os eventos viajam em lote.** Eles se acumulam na memória e partem juntos a cada
15 segundos, no máximo 50 por vez. Sem isso, um aluno mexendo na barra do vídeo
geraria dezenas de requisições por minuto.

**Cada aba tem uma identidade própria.** Um identificador aleatório (UUID v4) é
gerado por aba e guardado no `sessionStorage` — que, diferente do `localStorage`,
morre quando a aba fecha, que é exatamente o tempo de vida de uma sessão de
estudo. Ele é injetado automaticamente em todo evento, o que permite separar duas
abas do mesmo aluno. Ele não identifica a pessoa: o aluno já vem do token.

**O horário é convertido no servidor.** O navegador envia o horário em UTC (o
formato `...512Z`). O servidor converte para o fuso local antes de gravar. Sem
essa conversão, no Brasil todo evento apareceria 3 horas no futuro — o suficiente
para cair no dia errado e bagunçar o cálculo de inatividade.

---

## 9. O terceiro canal: a resposta do quiz

Os dois canais anteriores são "dispare e esqueça". O quiz é diferente: ele precisa
responder na hora se o aluno acertou. E precisa fazer isso **no servidor**.

Antes, a resposta certa ia junto com a pergunta, escondida num atributo do HTML —
qualquer aluno que abrisse as ferramentas de desenvolvedor do navegador via o
gabarito. Hoje o navegador envia só a alternativa marcada, e a comparação acontece
no Python. Na mesma requisição, o servidor ainda atualiza o modelo de domínio do
aluno e a agenda de revisão espaçada.

Há também uma proteção contra contagem dupla: o front reenvia o lote inteiro de
questões a cada clique, então o servidor verifica se aquela questão já foi
acertada antes e, em caso positivo, não gera nova tentativa nem novo evento.

---

## 10. Onde cada coisa mora, se você quiser ler o código

| Quero entender… | Arquivo |
|---|---|
| O cronômetro, os portões, o envio por delta | [OvaReader.tsx:224–344](Front-End/react-logic-demo/src/components/ova/OvaReader.tsx#L224-L344) |
| O `IntersectionObserver` das seções | [useSectionTracking.ts](Front-End/react-logic-demo/src/hooks/useSectionTracking.ts) |
| Os 100 baldes do vídeo, YouTube e HTML5 | [VideoPlayer.tsx](Front-End/react-logic-demo/src/components/players/VideoPlayer.tsx) |
| A fila de eventos e o `session_id` | [events.ts](Front-End/react-logic-demo/src/services/events.ts) |
| O `fetch` com token e `keepalive` | [api.ts:50–80](Front-End/react-logic-demo/src/services/api.ts#L50-L80) |
| O token HMAC e o `@require_auth` | [auth.py:70–120](Back-End/edubot/api/auth.py#L70-L120) |
| As rotas que gravam progresso | [progressRoute.py](Back-End/edubot/api/routes/progressRoute.py) |
| O vocabulário de 20 verbos | [events.py:33–46](Back-End/edubot/services/events.py#L33-L46) |
| O OU lógico do bitmap | [media.py](Back-End/edubot/services/media.py) |
| A correção do quiz no servidor | [questionRoute.py:194–273](Back-End/edubot/api/routes/questionRoute.py#L194-L273) |

---

## 11. Glossário

**API** — o conjunto de endereços que o servidor expõe para receber e devolver
dados. Aqui, coisas como `POST /progress/ova`.

**Bearer token** — literalmente "token ao portador": quem apresenta o token é
tratado como o dono dele. Vai num cabeçalho HTTP a cada requisição.

**Cabeçalho HTTP** — informação que acompanha a requisição sem fazer parte do
conteúdo, como o remetente num envelope.

**Delta** — a diferença desde a última vez, em vez do valor total. "Mais 15
segundos", não "195 segundos ao todo".

**Decorador (`@require_auth`)** — em Python, uma função que embrulha outra e roda
antes dela. Aqui, o porteiro que confere o crachá antes de a rota executar.

**HMAC-SHA256** — algoritmo que produz uma assinatura a partir de um texto e de
uma chave secreta. Quem não tem a chave não consegue forjar a assinatura.

**Idempotente** — operação que pode ser repetida sem mudar o resultado. Enviar a
mesma resposta certa duas vezes não cria duas tentativas.

**Marca d'água** — valor que só sobe, nunca desce, como a marca que a água deixa
na parede depois da enchente.

**ORM (Peewee)** — biblioteca que traduz objetos Python em comandos SQL.

**SPA (Single Page Application)** — site que carrega uma vez e reescreve a tela
com JavaScript em vez de recarregar a página a cada clique. É o caso do EduBot.

**UUID v4** — identificador aleatório de 128 bits, praticamente impossível de
repetir por acaso.

**xAPI** — padrão aberto para registrar experiências de aprendizagem na forma
"alguém — fez algo — em alguma coisa". O EduBot usa uma versão simplificada.

---

*Documento gerado em 18/09/2026 a partir de leitura direta do código de captura.
Todos os nomes de função, constantes e cabeçalhos citados existem nos arquivos
listados na seção 10.*
