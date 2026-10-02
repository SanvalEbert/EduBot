# API do EduBot — guia de integração

Você recebeu este pacote para ler dados do EduBot (uma plataforma de objetos de
aprendizagem com rastreamento de estudo) a partir da sua aplicação.

A integração é **somente-leitura** e acontece por HTTP: a sua aplicação chama a
API, apresentando uma chave. Você não recebe acesso ao banco de dados, e isso é
deliberado — a chave limita o que pode ser lido, é revogável e deixa registro de
uso, coisas que uma credencial de banco não faz.

---

## O que veio no pacote

| Arquivo | Para quê |
|---|---|
| `edubot_client.php` | O cliente. É o que você usa. Não precisa editar. |
| `config.php` | Configuração base. Não precisa editar. |
| `config.local.exemplo.php` | **Renomeie para `config.local.php` e preencha.** |
| `exemplo.php` | Demonstração executável de tudo que a API oferece. |
| `LEIA-ME.md` | Este arquivo. |

Você também deve ter recebido, **em mensagem separada**, dois valores:

- a **URL base** (algo como `https://...`)
- a **chave de API** (começa com `ek_live_`)

---

## Começando (3 minutos)

**1.** Renomeie `config.local.exemplo.php` para `config.local.php` e preencha a
URL e a chave.

**2.** Confirme que funciona:

```bash
php exemplo.php
```

A saída começa assim:

```
======================================================================
  1. Conexão e escopos da chave
======================================================================
Servidor : EduBot Public API v1
Chave    : <o nome que deram à sua chave>
Escopos  : catalog:read, tracking:read, metrics:read
```

A linha **Escopos** é importante: ela lista exatamente o que a sua chave pode
ler. Se faltar algo que você precisa, peça — é um ajuste de um comando do lado
de lá, e a API responde `403` com o nome do escopo que falta.

**3.** Use no seu código:

```php
require __DIR__ . '/edubot_client.php';
$edubot = new EduBotClient();

$ovas = $edubot->ovas();
foreach ($ovas as $ova) {
    echo $ova['ova_id'] . ' - ' . $ova['ova_name'] . PHP_EOL;
}
```

**Requisitos:** PHP 7.4 ou superior. A extensão cURL é recomendada; sem ela o
cliente usa `file_get_contents` automaticamente.

### Se a sua aplicação não é PHP

O cliente PHP é conveniência, não obrigação. A API é HTTP + JSON comum:

```bash
curl -H "X-API-Key: ek_live_SUA_CHAVE" https://SUA-URL/api/v1/catalog/ovas
```

Qualquer linguagem serve. O que segue vale igual.

---

## Endpoints

Todos são `GET`, todos sob `/api/v1/`, todos exigem o header
`X-API-Key: ek_live_...`.

| Endpoint | Método no cliente | Retorna |
|---|---|---|
| `/ping` | `ping()` | Diagnóstico: confirma chave e lista seus escopos |
| `/scopes` | `escopos()` | Todos os escopos e quais você tem |
| `/catalog/courses` | `cursos()` | Cursos |
| `/catalog/ovas` | `ovas()` | Objetos de aprendizagem |
| `/catalog/competencies` | `competencias()` | Competências |
| `/catalog/questions` | `questoes($ovaId)` | Questões |
| `/tracking/events` | `eventos()` / `eventosDesde()` | Eventos de estudo |
| `/tracking/progress` | `progresso()` | Progresso de leitura por OVA |
| `/tracking/sections` | `secoes()` | Leitura por seção do OVA |
| `/metrics/mastery` | `dominioPorCompetencia()` | Domínio médio por competência |
| `/metrics/questions` | `desempenhoPorQuestao()` | Taxa de acerto por questão |
| `/metrics/coverage` | `cobertura()` | Cobertura de conteúdo |
| `/metrics/engagement` | `engajamento()` | Volume de eventos por tipo |
| `/students` | `alunos()` | Alunos |

Comece por `ping()`. Ele responde em uma chamada se a URL, a chave e a rede
estão certas — e evita depurar as três coisas ao mesmo tempo.

---

## Os dados de rastreio

O núcleo da plataforma é `/tracking/events`: uma linha por sinal de estudo.

```json
{
  "event_id": 1843,
  "subject_id": "772b1bd50e715808",
  "verb": "read",
  "object_type": "ova",
  "object_id": 12,
  "context": { "perc": 40, "seconds": 65 },
  "occurred_at": "2026-09-21 19:53:42"
}
```

- **`verb`** — o que aconteceu: `opened`, `read`, `played`, `paused`, `seeked`,
  `answered`, `completed`, `asked_tutor`, `section_enter`, `section_exit`,
  `idle_start`, `idle_end`, entre outros.
- **`object_type` / `object_id`** — sobre o quê: `ova`, `ova_section`,
  `resource`, `question`, `session`.
- **`context`** — detalhes variáveis por verbo: percentual lido, segundos,
  acerto, tempo de resposta.
- **`subject_id`** — quem, de forma pseudonimizada. Veja abaixo.

### `subject_id`: como identificar o aluno

Você recebe `subject_id`, um identificador opaco de 16 caracteres, e não o
identificador real do aluno. Ele é **estável**: o mesmo aluno tem sempre o mesmo
`subject_id`, em todos os endpoints. Então você consegue agrupar todos os
eventos de uma pessoa, cruzar com o progresso dela e montar coortes — tudo que
uma análise exige — sem receber a identidade de ninguém.

Nome e matrícula só aparecem se a sua chave tiver o escopo `students:pii`, que é
concedido à parte e depende de base legal (LGPD). Se a sua aplicação realmente
precisa exibir nomes, diga qual é a finalidade — é uma conversa, não um bloqueio.

---

## Sincronização incremental

**Não** refaça a leitura completa a cada execução. Os eventos são paginados por
cursor: você guarda o último `event_id` processado e, na próxima rodada, só
recebe o que entrou depois.

```php
$ultimo = (int) @file_get_contents('cursor.txt');

foreach ($edubot->eventosDesde($ultimo) as $evento) {
    processar($evento);
    $ultimo = $evento['event_id'];
}

file_put_contents('cursor.txt', (string) $ultimo);
```

`eventosDesde()` cuida da paginação sozinho e devolve evento a evento, então a
memória não cresce com o tamanho da base. Cada evento chega exatamente uma vez.

Em HTTP puro, o mesmo padrão: passe `?after_id=<último>&limit=500` e siga
enquanto `next_after_id` não for `null`.

```json
{ "data": [ ... ], "count": 500, "next_after_id": 1843 }
```

É cursor e não `OFFSET` de propósito: a tabela cresce durante a varredura, e com
`OFFSET` você pularia ou repetiria linhas.

### Outros parâmetros

- `?since=` / `?until=` — recorte por data, ISO-8601 (`2026-09-01` ou
  `2026-09-01T14:30:00`). Data malformada devolve `400` em vez de ser ignorada.
- `?verb=` / `?object_type=` — filtram o tipo de evento.
- `?limit=` — até 500 por página.

---

## Erros

| Status | O que significa | O que fazer |
|---|---|---|
| `400` | Parâmetro malformado | A mensagem diz qual |
| `401` | Chave ausente, inválida, revogada ou expirada | Confira `config.local.php` |
| `403` | Chave válida, mas sem o escopo do endpoint | `escopos()` mostra o que você tem; peça o que falta |
| `429` | Requisições demais na janela | Use `limit` maior e faça menos chamadas |

Toda falha volta como JSON: `{"error": "...", "status": 403}`. O cliente PHP
lança `EduBotApiException`, com a mensagem já traduzida:

```php
try {
    $dados = $edubot->eventos();
} catch (EduBotApiException $e) {
    error_log($e->getMessage());
    error_log('status HTTP: ' . $e->statusHttp);
}
```

---

## Cuidados com a chave

**A chave só pode existir no seu servidor.** Nunca a coloque em JavaScript de
navegador, em app mobile ou em repositório público — em qualquer um desses casos
ela é legível por quem quiser. Se você precisa exibir os dados num front-end, o
seu backend chama a API e repassa ao front apenas o que aquela tela precisa.

Outros pontos:

- Mantenha `config.local.php` fora do controle de versão.
- Ela pode ter prazo de validade. Se começar a vir `401` do nada, provavelmente
  expirou — peça outra.
- Se suspeitar que vazou, avise imediatamente: revogar leva segundos, e o
  estrago de não revogar, não.
- Os dados são de estudantes reais. Trate-os com o cuidado que isso exige,
  inclusive nos seus próprios logs.
