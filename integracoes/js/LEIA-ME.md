# EduBot Tracker: coletar interações de um material HTML

Um script JavaScript que você inclui no seu material. Ele captura os cliques nos
elementos que você marcar, mais a abertura e o tempo de página, e envia tudo
para o EduBot, que grava no MySQL.

Não tem dependências nem etapa de build: é um arquivo só, `edubot-tracker.js`.

---

## 1. Incluir no material

Copie `edubot-tracker.js` para junto do seu HTML e coloque antes de `</body>`:

```html
<script src="edubot-tracker.js"
        data-endpoint="http://localhost:5010"
        data-key="ek_live_SUA_CHAVE_DE_COLETA"></script>
```

- `data-endpoint` é a URL do EduBot. Por enquanto ele roda local, na máquina do
  Victor (`http://localhost:5010`).
- `data-key` é a chave de coleta. Ela **só grava eventos** e não lê nada, então
  pode ficar no HTML sem problema.

Opcionais: `data-user-id="..."` (id do usuário no seu sistema, se houver) e
`data-debug="true"` (mostra cada evento no console do navegador).

## 2. Marcar o que rastrear

Qualquer um dos dois jeitos funciona:

```html
<!-- por atributo: o valor vira o nome do alvo -->
<button data-edubot-track="botao-iniciar">Iniciar</button>

<!-- por classe: o nome do alvo vem do id -->
<button class="edubot-track" id="botao-proximo">Próximo</button>
```

Para mandar informação extra junto com o clique, use `data-edubot-context` com
um JSON:

```html
<button data-edubot-track="questao-3"
        data-edubot-context='{"questao": 3, "alternativa": "b", "correta": true}'>
  b) 42
</button>
```

O clique conta mesmo se o elemento clicado for um filho do marcado (um ícone
dentro do botão, por exemplo).

## 3. O que é enviado

| Evento | Quando | `context` |
|---|---|---|
| `page_view` | o script inicia | idioma, tamanho da tela, se está num iframe |
| `click` | clique num elemento marcado | tag, texto, `href`/`value` e o `data-edubot-context` |
| `page_hidden` | a aba fica oculta | `visible_seconds` |
| `page_exit` | a página fecha | `visible_seconds`, `total_seconds` |
| (o seu) | `EduBotTracker.track(...)` | o que você passar |

Todo evento vai com:

- `visitor_id`: id anônimo do navegador, que se mantém entre visitas.
- `session_id`: um por carregamento da página.
- A URL e o título da página.
- O horário.

Os eventos são enviados em lote a cada ~3 s. Ao fechar a página, o que sobrou
na fila vai por `sendBeacon`.

## 4. Eventos manuais (JavaScript)

```js
EduBotTracker.track('video_play', 'video-introducao', { segundo: 0 });
EduBotTracker.identify('aluno-123');     // associa os próximos eventos a um usuário
EduBotTracker.flush();                   // força o envio agora
EduBotTracker.getVisitorId();
```

O nome do evento aceita letras, números e `_ . : -`, com até 40 caracteres.

Para iniciar pelo código em vez de pelos atributos da tag:

```html
<script src="edubot-tracker.js"></script>
<script>
  EduBotTracker.init({ endpoint: 'http://localhost:5010', key: 'ek_live_...', debug: true });
</script>
```

Para mostrar o status na página:

```js
document.addEventListener('edubot-tracker:sent',  e => console.log('gravado', e.detail));
document.addEventListener('edubot-tracker:error', e => console.log('erro', e.detail));
```

## 5. Testar

`exemplo.html`, nesta pasta, é uma página pronta com botões marcados de vários
jeitos e um log do que foi enviado. Abra no navegador, cole a URL e a chave e
clique. Cada envio mostra `ENVIADO: N evento(s) gravado(s) no banco`.

Se algo der errado, o motivo aparece no console como `[EduBotTracker] ...`:

| Mensagem | Causa |
|---|---|
| `lote descartado (401)` | chave errada ou revogada |
| `lote descartado (403)` | a chave não tem o escopo `events:write` |
| `envio falhou (Failed to fetch)` | EduBot fora do ar ou URL errada; o script tenta de novo sozinho |

## 6. Formato do envio (se quiser mandar sem o script)

`POST {endpoint}/api/v1/collect`, corpo JSON (`Content-Type` `application/json`
ou `text/plain`):

```json
{
  "key": "ek_live_...",
  "visitor_id": "a1b2c3d4e5f60718",
  "session_id": "9f8e7d6c5b4a3921",
  "user_id": null,
  "page_url": "https://.../material.html",
  "page_title": "Material de teste",
  "events": [
    { "type": "click", "target": "botao-iniciar",
      "context": { "tag": "button" }, "occurred_at": "2026-09-23T17:00:00.000Z" }
  ]
}
```

Resposta: `{"accepted": 1, "errors": 0, "rejected": []}`. Os limites são:

- Até 50 eventos por requisição.
- `context` com até 2 KB.
- `visitor_id` e `session_id` com 8 a 64 caracteres (`A-Z a-z 0-9 _ -`).

Um item inválido é rejeitado com o motivo, e o resto do lote é gravado.

## 7. Dentro do Canvas (próxima etapa)

O script já funciona dentro de iframe de outro domínio (testado). Dois pontos
para quando formos para o Canvas:

- **Identidade.** Sem login, o aluno é um `visitor_id` anônimo. Se o navegador
  bloquear o armazenamento dentro do iframe, esse id muda a cada carregamento.
  Para saber quem é o aluno, precisamos do id vindo do Canvas (LTI) e passá-lo
  em `data-user-id`.
- **Endereço.** A página do Canvas é HTTPS. Para chamar o EduBot rodando local,
  o navegador pede permissão de "acesso à rede local". Para uso real, o EduBot
  precisa estar num servidor com HTTPS.
