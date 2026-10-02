# Integração externa — abrindo os dados do EduBot para um parceiro

Guia de implantação da API que permite a um sistema de terceiros ler os dados do
EduBot (catálogo, rastreio, métricas e alunos) sem receber acesso ao MySQL.

**Escrito para:** quem vai operar a integração do lado do EduBot e quem vai
consumi-la do lado de fora.

- **Vai liberar o acesso?** Seções 1 a 5 — migration, segredos, emissão da chave.
- **Vai consumir os dados?** Seções 6 a 9 — como o mecanismo funciona, o passo a
  passo de leitura, os endpoints e os erros. Comece pela **seção 7**.
- **Vai repassar para um parceiro?** Seção 10.

---

## O que NÃO fazer, e por quê

A solução aparentemente mais rápida é abrir a porta `3310` do MySQL e mandar as
credenciais do banco para a pessoa. Não faça isso:

| Problema | Consequência concreta |
|---|---|
| A credencial `eduardo` tem INSERT/UPDATE/DELETE | Um erro no script do parceiro apaga progresso real de aluno |
| Não há filtro de linha | Ele lê nome, RA e senha de todos os alunos, inclusive os que não são do piloto |
| Não há trilha de acesso | Perante a LGPD você não consegue responder quem leu qual dado pessoal, nem quando |
| Revogar exige trocar a senha do banco | E isso derruba o Flask junto, porque é a mesma credencial |
| MySQL exposto na internet | Alvo de varredura automatizada em questão de horas |

O que este guia implanta é o contrário disso: uma porta HTTP somente-leitura,
com credencial por parceiro, escopo declarado, pseudonimização por padrão e
contagem de uso por chave.

---

## Os dois caminhos

Ambos estão implementados. Eles expõem **o mesmo contrato JSON**, então o mesmo
cliente PHP serve aos dois.

```
CAMINHO A (recomendado)
  App PHP do parceiro  ──HTTP + X-API-Key──▶  Flask /api/v1/*  ──▶  MySQL
                                              (chaves em banco, escopos testados)

CAMINHO B (alternativo)
  App do parceiro  ──HTTP + X-API-Key──▶  api.php (PDO)  ──▶  MySQL
                                          (usuário SOMENTE-LEITURA, chaves em arquivo)
```

**Use o A** se o Flask já está no ar. As chaves ficam em banco (revogar é um
comando, não uma edição de arquivo), as regras de escopo têm 47 testes
automatizados, e a política de acesso mora num lugar só.

**Use o B** se a hospedagem disponível é PHP/cPanel e subir Python não é opção.
Ele é autônomo, mas é uma **segunda porta**: endpoint novo que você criar no
Flask não aparece nele automaticamente.

---

## Escopos

Uma chave só lê o que o escopo dela declara. Conceder um não concede os outros.

| Escopo | Libera | Contém dado pessoal? |
|---|---|---|
| `catalog:read` | OVAs, competências, questões, cursos | Não |
| `tracking:read` | Eventos de aprendizado, progresso, leitura por seção | Pseudonimizado |
| `metrics:read` | Domínio por competência, cobertura, engajamento, item-analysis | Não (agregado) |
| `students:read` | Lista de alunos (pseudônimo, curso, papel) | Pseudonimizado |
| `students:pii` | **Nome e RA do aluno** | **Sim — exige base legal** |
| `events:write` | **Gravar** eventos pelo `edubot-tracker.js` (não lê nada) | Não se aplica |

`events:write` é o único escopo de escrita e o único cuja chave fica no
navegador (no HTML do material). Por isso o `apikey_tool` recusa combiná-lo com
qualquer escopo de leitura: emita uma chave só para coletar e outra para ler.
Ver [§11](#11-coleta-pelo-navegador-edubot-trackerjs).

Sobre a **pseudonimização**: o parceiro recebe `subject_id`, um hash estável de
16 caracteres. Estável porque ele precisa correlacionar os eventos do mesmo aluno
ao longo do tempo; opaco porque não deve conseguir chegar à pessoa. O salt é o
`EDUBOT_PSEUDONYM_SALT` — trocá-lo rotaciona todos os pseudônimos de uma vez.

`students:pii` é deliberadamente um escopo à parte. Conceder rastreio não
concede nome e RA junto; é preciso pedir os dois.

---

## 1. Aplicar a migration

Cria a tabela `api_keys`. É idempotente — rodar duas vezes não faz mal.

```bash
docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db \
  < Database/sql/migration_021_api_keys.sql
```

> Num banco criado do zero (volume novo) o arquivo já roda sozinho pelo
> `docker-entrypoint-initdb.d`. O comando acima é para o volume que já existe —
> o mesmo gotcha das migrations anteriores.

## 2. Definir os segredos

No `.env` da raiz do projeto:

```bash
# Salt da pseudonimização. Gere com:
#   python -c "import secrets; print(secrets.token_hex(32))"
EDUBOT_PSEUDONYM_SALT=cole-aqui-um-valor-longo-e-aleatorio

# Teto por chave (opcional; os valores abaixo são os padrões)
EDUBOT_APIKEY_RATE_LIMIT=120
EDUBOT_APIKEY_RATE_WINDOW=60
```

E repasse-os ao container, em `compose.yaml`, no bloco `environment` do
`ova_flask` — **sem esta linha o valor do `.env` não chega ao container**:

```yaml
      EDUBOT_PSEUDONYM_SALT: ${EDUBOT_PSEUDONYM_SALT:-}
      EDUBOT_APIKEY_RATE_LIMIT: ${EDUBOT_APIKEY_RATE_LIMIT:-120}
      EDUBOT_APIKEY_RATE_WINDOW: ${EDUBOT_APIKEY_RATE_WINDOW:-60}
```

Depois: `docker compose up -d ova_flask`.

## 3. Emitir a chave do parceiro

```bash
docker exec -it ova_back_end python -m tools.apikey_tool criar \
  --nome "Piloto Parceiro X" \
  --escopos catalog:read,tracking:read,metrics:read \
  --dias 90 \
  --notas "contato: fulano@exemplo.br"
```

A chave em claro aparece **uma única vez**. O banco guarda só o SHA-256, então
não existe comando para exibi-la depois — se o parceiro perder, revogue e emita
outra. Entregue por canal seguro (não por e-mail em texto aberto).

```bash
docker exec -it ova_back_end python -m tools.apikey_tool listar    # sem segredos
docker exec -it ova_back_end python -m tools.apikey_tool revogar --prefixo ek_live_3f9aK2
docker exec -it ova_back_end python -m tools.apikey_tool escopos
```

Comece com o escopo mínimo. Ampliar depois é um comando; recolher um dado que já
saiu, não.

## 4. Conferir

```bash
curl -s http://localhost:5010/api/v1/ping -H "X-API-Key: ek_live_..."
```

```json
{"ok": true, "key_name": "Piloto Parceiro X",
 "scopes": ["catalog:read", "tracking:read", "metrics:read"], ...}
```

Sem chave deve vir `401`; com escopo faltando, `403`.

---

## 5. Caminho B — a API PHP autônoma

Só se você escolheu o Caminho B. Se ficou no A, pule para a seção 6.

**5.1. Criar o usuário somente-leitura.** Abra
`Database/sql/usuario_somente_leitura.sql`, troque `TROQUE-ESTA-SENHA` por uma
senha forte e aplique:

```bash
docker exec -i ova_db mysql -uroot -pPassword-1 < Database/sql/usuario_somente_leitura.sql
docker exec -i ova_db mysql -uroot -pPassword-1 -e "SHOW GRANTS FOR 'edubot_leitura'@'%';"
```

A saída deve mostrar **apenas `SELECT`**. O arquivo concede tabela a tabela, e a
coluna `student_name`/`ra` fica de fora por padrão — há um bloco comentado no fim
para o caso de você ter base legal para incluí-las.

**5.2. Publicar os arquivos.** Copie `integracoes/php/` para o servidor web
(`/var/www/html/edubot/`, `public_html/edubot/` etc.).

**5.3. Configurar.** No servidor:

```bash
cp config.php config.local.php
php -r "echo 'ek_php_'.bin2hex(random_bytes(24)).PHP_EOL;"   # gera uma chave
```

Edite `config.local.php` com a senha do `edubot_leitura`, a chave gerada e **o
mesmo** `EDUBOT_PSEUDONYM_SALT` do Flask — se os salts divergirem, os dois
caminhos geram `subject_id` diferentes para o mesmo aluno e o parceiro não
consegue cruzar os dados.

**5.4. Testar.**

```bash
curl -s "http://localhost/edubot/api.php?recurso=ping" -H "X-API-Key: ek_php_..."
curl -s "http://localhost/edubot/api.php?recurso=ovas" -H "X-API-Key: ek_php_..."
```

**Requisitos:** PHP 7.4+ com `pdo_mysql`. Em produção, sirva por HTTPS — a chave
viaja no header e, em HTTP puro, em claro.

---

## 6. Como funciona por dentro

Antes do passo a passo, o caminho que uma requisição percorre. Entender isto
economiza a maior parte das dúvidas de integração, porque quase todo erro que
aparece é um destes cinco estágios reprovando.

```
  GET /api/v1/tracking/events?after_id=120&limit=500
  X-API-Key: ek_live_...
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. A chave vira SHA-256 e é buscada em `api_keys`.          │  → 401 se não achar,
  │    O segredo nunca é comparado em claro, nem existe          │    estiver revogada
  │    em claro no banco.                                        │    ou expirada
  ├─────────────────────────────────────────────────────────────┤
  │ 2. Teto de requisições da janela (120/min por chave).       │  → 429 se estourar
  ├─────────────────────────────────────────────────────────────┤
  │ 3. O endpoint declara o escopo que exige; a chave           │  → 403 se faltar,
  │    precisa tê-lo. `tracking:read` neste caso.                │    dizendo qual
  ├─────────────────────────────────────────────────────────────┤
  │ 4. Consulta ao MySQL, já recortada pelos filtros da query.  │
  ├─────────────────────────────────────────────────────────────┤
  │ 5. Pseudonimização: `student_id` sai, entra `subject_id`.   │
  │    Texto livre do aluno é removido. Sem `students:pii`,      │
  │    nome e RA nem chegam a ser selecionados.                  │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  { "data": [...], "count": 500, "next_after_id": 620 }
  + a chave tem `request_count` e `last_used_at` atualizados
```

Três consequências que valem guardar:

- **Nada aqui escreve nos dados do EduBot.** O único `UPDATE` de todo o caminho é
  o contador de uso da própria chave.
- **O escopo é verificado por endpoint, não por chave.** Uma chave com quatro
  escopos atravessa quatro portas diferentes; perder um escopo não derruba os
  outros.
- **A pseudonimização acontece na saída, não no banco.** Os dados continuam
  íntegros internamente; o recorte é de quem lê.

### `subject_id`: como o aluno é identificado

Em vez do `student_id` real, sai um hash de 16 caracteres derivado de
`SHA-256(salt + ":" + student_id)`.

Ele é **estável** — o mesmo aluno tem sempre o mesmo `subject_id`, em todos os
endpoints e em todas as requisições. É isso que permite ao consumidor juntar os
eventos de uma pessoa, cruzar com o progresso dela e montar coortes. E é
**opaco** — sem o salt, não há caminho de volta ao aluno.

Trocar o `EDUBOT_PSEUDONYM_SALT` rotaciona todos os pseudônimos de uma vez. Útil
ao encerrar um convênio; destrutivo se feito sem aviso, porque quebra a
correlação histórica de quem já consumia.

---

## 7. Passo a passo: puxando os dados pela API

Escrito para quem vai **consumir**. Os exemplos usam `curl` porque funcionam em
qualquer lugar; há o equivalente em PHP e Python no fim de cada passo.

### Passo 1 — receber os dois valores

Do responsável pelo EduBot vêm a **URL base** e a **chave**. A chave vai no
header `X-API-Key` de toda requisição. Não há login, nem token para renovar, nem
sessão para manter.

```bash
export EDUBOT_URL="https://seu-servidor-edubot"
export EDUBOT_KEY="ek_live_..."
```

### Passo 2 — confirmar que o acesso funciona

Sempre comece por aqui. `ping` responde em uma chamada se a URL, a chave e a
rede estão certas — e evita depurar as três coisas ao mesmo tempo depois.

```bash
curl -s -H "X-API-Key: $EDUBOT_KEY" "$EDUBOT_URL/api/v1/ping"
```

```json
{
  "ok": true,
  "service": "EduBot Public API",
  "version": "v1",
  "server_time": "2026-09-23T00:12:18",
  "key_name": "Captura doc",
  "scopes": ["catalog:read", "tracking:read", "metrics:read", "students:read"]
}
```

O campo **`scopes` é a resposta mais importante desta chamada**: ele lista
exatamente o que a sua chave pode ler. Se algo que você precisa não estiver ali,
peça — é um comando do lado de lá, não um impedimento técnico.

### Passo 3 — ler o catálogo (o mais simples, para calibrar)

O catálogo não tem dado pessoal, então é o melhor lugar para validar o seu
código de consumo antes de tocar em rastreio.

```bash
curl -s -H "X-API-Key: $EDUBOT_KEY" "$EDUBOT_URL/api/v1/catalog/ovas"
```

```json
{
  "data": [
    { "ova_id": 1, "ova_name": "Computação Quântica", "subject_id": 1,
      "num_interactions": 19, "link": "quantum_computing.html",
      "quiz_gate_perc": 70, "subject_name": "Computação Quântica" }
  ],
  "count": 4
}
```

Todo endpoint de listagem devolve o mesmo envelope: `data` com as linhas e
`count` com quantas vieram.

### Passo 4 — puxar o rastreio

Este é o dado central. Uma linha por sinal de estudo:

```bash
curl -s -H "X-API-Key: $EDUBOT_KEY" \
     "$EDUBOT_URL/api/v1/tracking/events?limit=2"
```

```json
{
  "data": [
    {
      "event_id": 1,
      "subject_id": "542ad51483739548",
      "verb": "completed",
      "object_type": "ova",
      "object_id": 1,
      "context": { "perc": 100 },
      "occurred_at": "2026-09-03 23:03:11"
    },
    {
      "event_id": 2,
      "subject_id": "542ad51483739548",
      "verb": "received_intervention",
      "object_type": "intervention",
      "object_id": 1,
      "context": { "tipo": "trilha_minima", "trigger": "ova_completed" },
      "occurred_at": "2026-09-03 23:03:11"
    }
  ],
  "count": 2,
  "next_after_id": 2
}
```

Os campos:

| Campo | O que é |
|---|---|
| `event_id` | Identificador crescente. **É o cursor** — veja o passo 5 |
| `subject_id` | O aluno, pseudonimizado e estável |
| `verb` | `opened`, `read`, `played`, `paused`, `seeked`, `answered`, `completed`, `asked_tutor`, `section_enter`, `section_exit`, `idle_start`, `idle_end`, entre outros |
| `object_type` / `object_id` | Sobre o quê: `ova`, `ova_section`, `resource`, `question`, `intervention`, `session` |
| `context` | JSON variável por verbo: `perc`, `seconds`, `correct`, `response_ms` |
| `occurred_at` | Quando aconteceu, no relógio do servidor |

Filtros disponíveis: `?since=` e `?until=` (ISO-8601), `?verb=`,
`?object_type=`, `?subject_id=`.

### Passo 5 — percorrer tudo sem pular nem repetir

Aqui está a parte que mais dá errado quando se improvisa. **Não use `OFFSET`.** A
tabela de eventos cresce enquanto você varre: com `OFFSET`, linhas novas empurram
as antigas e você pula ou duplica registros.

A API pagina por **cursor**. Cada resposta traz `next_after_id`; passe-o como
`?after_id=` na chamada seguinte. Quando vier `null`, acabou.

```bash
cursor=0
while : ; do
  resp=$(curl -s -H "X-API-Key: $EDUBOT_KEY" \
         "$EDUBOT_URL/api/v1/tracking/events?after_id=$cursor&limit=500")
  echo "$resp" | jq -c '.data[]'          # processe aqui
  cursor=$(echo "$resp" | jq -r '.next_after_id')
  [ "$cursor" = "null" ] && break
done
```

**Guarde o último `event_id` processado.** Na próxima execução, comece dele: só
chega o que entrou depois. É assim que uma sincronização diária não reprocessa a
base inteira todo dia.

```php
// PHP — o cliente cuida da paginação sozinho
$ultimo = (int) @file_get_contents('cursor.txt');
foreach ($edubot->eventosDesde($ultimo) as $ev) {
    processar($ev);
    $ultimo = $ev['event_id'];
}
file_put_contents('cursor.txt', (string) $ultimo);
```

```python
# Python — mesma lógica
import requests, pathlib
h = {"X-API-Key": CHAVE}
cursor = int(pathlib.Path("cursor.txt").read_text() or 0)
while True:
    r = requests.get(f"{URL}/api/v1/tracking/events",
                     headers=h, params={"after_id": cursor, "limit": 500}).json()
    for ev in r["data"]:
        processar(ev)
        cursor = ev["event_id"]
    if r["next_after_id"] is None:
        break
pathlib.Path("cursor.txt").write_text(str(cursor))
```

### Passo 6 — progresso e métricas

Progresso é o acumulado por (aluno, OVA) — quanto tempo leu, quanto rolou, se
concluiu:

```json
{
  "data": [
    { "progress_id": 1, "subject_id": "542ad51483739548", "ova_id": 1,
      "read_time_seconds": 900, "perc_scrolled": 100,
      "completed": true, "last_access": "2026-09-03 23:03:11" }
  ],
  "count": 2,
  "next_after_id": 2
}
```

Métricas já vêm agregadas, sem indivíduo:

```json
{
  "data": [
    { "competency_id": 3,
      "competencia": "Reconhecer os desafios e limitações técnicos da computação quântica",
      "dominio_medio": 0.3302, "alunos": 5, "tentativas": 16 }
  ],
  "count": 9
}
```

O campo `alunos` vem junto de propósito: uma média de domínio sobre 2 alunos não
significa o mesmo que sobre 200, e sem o N quem consome não tem como saber.

### Passo 7 — automatizar

Uma linha no cron, rodando a sincronização incremental:

```cron
0 3 * * *  /usr/bin/php /var/www/edubot/sincronizar.php >> /var/log/edubot-sync.log 2>&1
```

Dimensionamento: o teto é de **120 requisições por minuto** por chave, e cada
página traz até **500 registros**. Ou seja, até 60 mil eventos por minuto — folga
larga para qualquer sincronização diária. Se você estiver batendo no `429`,
quase sempre a causa é `limit` pequeno demais, não volume de dados.

---

## 8. Endpoints

Todos exigem chave e ficam sob `/api/v1/`. Todos são `GET`, exceto o `POST /collect` do tracker ([§11](#11-coleta-pelo-navegador-edubot-trackerjs)).

| Caminho A (Flask) | Caminho B (PHP) | Escopo | Retorna |
|---|---|---|---|
| `/ping` | `?recurso=ping` | — | Diagnóstico e escopos da chave |
| `/scopes` | — | — | Catálogo de escopos e o que a chave tem |
| `/catalog/courses` | `?recurso=cursos` | `catalog:read` | Cursos |
| `/catalog/ovas` | `?recurso=ovas` | `catalog:read` | OVAs (`?subject_id=`) |
| `/catalog/competencies` | `?recurso=competencias` | `catalog:read` | Competências |
| `/catalog/questions` | `?recurso=questoes` | `catalog:read` | Questões (`?ova_id=`, `?include_answer=1`) |
| `/tracking/events` | `?recurso=eventos` | `tracking:read` | Eventos (`?since=`, `?verb=`, `?after_id=`) |
| `/tracking/progress` | `?recurso=progresso` | `tracking:read` | Progresso por OVA |
| `/tracking/sections` | `?recurso=secoes` | `tracking:read` | Leitura por seção |
| `/metrics/mastery` | `?recurso=dominio` | `metrics:read` | Domínio médio por competência |
| `/metrics/questions` | `?recurso=questoes_desempenho` | `metrics:read` | Taxa de acerto por questão |
| `/metrics/coverage` | — | `metrics:read` | Cobertura de conteúdo |
| `/metrics/engagement` | `?recurso=engajamento` | `metrics:read` | Eventos por verbo |
| `/students` | `?recurso=alunos` | `students:read` | Alunos (`?course_id=`) |
| `/collect/events` | — | `tracking:read` | Eventos do tracker (`?type=`, `?visitor_id=`, `?key_id=`) |
| `POST /collect` | — | `events:write` | Grava um lote do tracker (chave pode ir no corpo) |

**Paginação:** `?limit=` (máx. 500) + `?after_id=`.
**Datas:** `?since=` / `?until=` em ISO-8601 (`2026-09-01` ou `2026-09-01T14:30:00`).
Data malformada devolve `400` — não é ignorada em silêncio.

---

## 9. Erros

Toda falha volta como JSON, com a mesma forma. Exemplos reais:

```json
{ "error": "Chave de API ausente, inválida ou revogada.", "status": 401 }
{ "error": "Chave sem permissão. Escopo(s) necessário(s): tracking:read.", "status": 403 }
```

| Status | Significa | O que fazer |
|---|---|---|
| `400` | Parâmetro malformado | A mensagem diz qual |
| `401` | Chave ausente, inválida, revogada ou expirada | Conferir o header `X-API-Key` |
| `403` | Chave válida, escopo insuficiente | A mensagem nomeia o escopo; `GET /scopes` mostra o que você tem |
| `429` | Teto de requisições estourado | Aumentar `limit` e fazer menos chamadas |
| `500` | Erro no servidor | Reportar — não é problema do consumidor |

Note a diferença entre `401` e `403`: **`401` é "não sei quem você é"**, **`403`
é "sei quem você é, e isso você não pode ler"**. O `403` sempre diz qual escopo
falta, para que a conversa seja objetiva.

---

## 10. Para entregar ao parceiro

Mande o `edubot-api-parceiro.zip` (cliente PHP, exemplo executável e o
`LEIA-ME.md` escrito para quem consome). A **URL e a chave vão em mensagem
separada** — anexo circula e é arquivado; a chave não deve viajar junto.

Consumo mínimo, sem dependência nenhuma:

```php
<?php
$ch = curl_init('https://SEU-SERVIDOR/api/v1/catalog/ovas');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER     => ['X-API-Key: ek_live_SUA_CHAVE'],
]);
$dados = json_decode(curl_exec($ch), true);
curl_close($ch);

foreach ($dados['data'] as $ova) {
    echo $ova['ova_id'] . ' - ' . $ova['ova_name'] . PHP_EOL;
}
```

Com o cliente pronto, `php exemplo.php` exercita a integração inteira e imprime
o resultado de cada bloco — serve como teste de fumaça do outro lado.


---

## 11. Coleta pelo navegador (`edubot-tracker.js`)

O caminho inverso das seções anteriores: em vez de um parceiro **ler** do
EduBot, um material HTML de fora (um OVA de parceiro, uma página de teste, e
depois o Canvas) **envia** interações para o EduBot.

```
material.html + edubot-tracker.js  --POST /api/v1/collect-->  Flask  -->  collected_events
     (clique, page_view, tempo)          chave events:write
```

**Preparar (uma vez):**

```bash
# tabela collected_events
docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db < Database/sql/migration_022_collected_events.sql

# chave de coleta (só grava)
docker exec -it ova_back_end python -m tools.apikey_tool criar     --nome "Material de teste Lucas" --escopos events:write --dias 30
```

**Entregar** ao autor do material: `integracoes/js/edubot-tracker.js`,
`exemplo.html` e o [LEIA-ME](integracoes/js/LEIA-ME.md) (como incluir, como
marcar botões e o formato do envio), mais a URL e a chave de coleta.

**Conferir no banco:**

```sql
SELECT event_id, event_type, target, visitor_id, context, origin, occurred_at
FROM collected_events ORDER BY event_id DESC LIMIT 20;
```

ou pela API, com uma chave `tracking:read`:
`GET /api/v1/collect/events?type=click&visitor_id=...` (mesmo cursor
`after_id` das outras rotas).

**Por que uma tabela separada de `learning_events`:** aquela exige um aluno do
EduBot e um verbo do enum fechado, e alimenta o domínio por competência, o
painel do tutor e o agente. O material externo não tem login, e o autor escolhe
o nome dos eventos. Misturar os dois poluiria as métricas pedagógicas com
eventos de teste. Quando houver identidade real (LTI no Canvas), `user_ref` é a
ponte para promover esses eventos a `learning_events`.

**Diferenças em relação ao resto da `/api/v1`:**

- **CORS aberto** (`EDUBOT_COLLECT_ORIGINS`, padrão `*`, inclusive `file://`).
- **A chave pode ir no corpo.** O `sendBeacon`, usado ao fechar a página, não
  manda header.
- **Teto próprio:** `EDUBOT_COLLECT_RATE_LIMIT`, padrão 600/min por chave,
  porque a turma inteira compartilha a mesma chave.

**Limitações conhecidas:**

- O visitante é anônimo (`visitor_id` no `localStorage`). Num iframe com
  storage bloqueado, esse id muda a cada carregamento.
- Como a chave é pública, qualquer pessoa que a copie pode gravar eventos falsos
  nessa chave. Isso não é problema para teste. Em produção, restrinja
  `EDUBOT_COLLECT_ORIGINS` ao domínio do material e revogue a chave ao fim do
  piloto.

## Notas de segurança

**A chave de leitura só existe em servidor.** Nunca a coloque em JavaScript de
navegador — seria o mesmo que publicá-la. É por isso que o CORS do Flask não
inclui `/api/v1`: a integração de leitura é servidor-a-servidor. A única exceção
é a chave `events:write` do tracker, pública por desenho: ela só grava em
`collected_events` e não lê nenhuma tabela. Se o parceiro precisa exibir os
dados num front, o backend dele chama a API e repassa o que for necessário.

**HTTPS em produção.** A chave viaja no header; em HTTP puro, qualquer ponto do
caminho a lê. E mantenha `EDUBOT_VERIFY_TLS = true`: desligar a verificação de
certificado entrega a chave a quem estiver no meio.

**LGPD.** `students:pii` expõe nome e RA. Antes de conceder: registre a base
legal (contrato, termo de consentimento ou finalidade de pesquisa aprovada),
prefira prazo de validade (`--dias`), e guarde o `listar` como evidência de quem
teve acesso e até quando. A revogação é `active = 0`, não `DELETE`, justamente
para preservar a trilha.

**O que nunca sai:** `student_password` não é selecionada em nenhum caminho, com
ou sem `students:pii`. O gabarito das questões só sai com `?include_answer=1`
explícito. Texto livre escrito pelo aluno (`context.text` de `asked_tutor`) é
removido sem `students:pii`.

---

## Arquivos

| Arquivo | Papel |
|---|---|
| `Database/sql/migration_021_api_keys.sql` | Tabela `api_keys` |
| `Database/sql/usuario_somente_leitura.sql` | Usuário MySQL só-SELECT (Caminho B) |
| `Back-End/edubot/data/models/api_keys.py` | Model Peewee |
| `Back-End/edubot/api/apikey.py` | `require_api_key`, escopos, pseudonimização |
| `Back-End/edubot/api/routes/publicApiRoute.py` | Endpoints `/api/v1/*` |
| `Back-End/tools/apikey_tool.py` | Criar, listar e revogar chaves |
| `Back-End/tests/test_public_api.py` | 47 testes (auth, escopo, LGPD, cursor) |
| `integracoes/php/config.php` | Modelo de configuração |
| `integracoes/php/edubot_client.php` | Cliente PHP (Caminho A) |
| `integracoes/php/api.php` | API PHP autônoma (Caminho B) |
| `integracoes/php/exemplo.php` | Demonstração executável |
| `Database/sql/migration_022_collected_events.sql` | Tabela `collected_events` (coleta) |
| `Back-End/edubot/data/models/collected_events.py` | Model Peewee da coleta |
| `Back-End/edubot/api/routes/collectRoute.py` | `POST /api/v1/collect` e `GET /api/v1/collect/events` |
| `Back-End/tests/test_collect.py` | 27 testes (chave, escopo, CORS, sendBeacon, lote) |
| `integracoes/js/edubot-tracker.js` | Script de coleta para incluir no material |
| `integracoes/js/exemplo.html` | Página de teste com botões marcados e log de envio |
| `integracoes/js/LEIA-ME.md` | Guia para quem vai incluir o script |
