# Guia da Plataforma — Como funciona e como testar

Este documento explica **como a plataforma de OVAs está funcionando hoje** e dá um
**passo a passo prático** para testar cada funcionalidade — com foco nas duas
entregas mais recentes:

1. **Migração do leitor de OVA para o front novo** (React nativo, dentro do
   dashboard — sem mais o leitor legado em outra aba).
2. **Assistente de IA por OVA** (chat lateral que conversa **só** sobre o
   conteúdo que o aluno está lendo).

---

## 1. Visão geral da arquitetura

| Camada | Tecnologia | Onde roda |
|--------|-----------|-----------|
| **Banco** | MySQL 8.4 (scripts DDL/DML em `Database/sql/`) | container `ova_db` — porta host **3310** |
| **Back-End** | Flask + Peewee (ORM) | container `ova_back_end` — porta host **5010** |
| **Front-End novo** | React 18 + TypeScript + Vite + Tailwind | compilado pelo container `ova_react_build`, servido pelo Apache |
| **Front-End (Apache)** | Apache HTTPD | container `ova_front_end` — porta host **8010** |

- **App novo (React):** http://localhost:8010/app/
- **API:** http://localhost:8010 → na verdade a API responde em http://localhost:5010

> O React é compilado **dentro do Docker** (`ova_react_build` roda `npm install`
> + `vite build` e emite em `Front-End/files/app`, que o Apache serve em `/app/`).
> Não é preciso ter Node instalado na máquina para *rodar* — só para desenvolver
> com hot-reload.

### Fluxo de dados (resumido)

```
Aluno (navegador, /app/)
   │  login (RA/senha)  ──────────────►  POST /login  ──►  token Bearer
   │  perfil completo   ──────────────►  GET  /student/me
   │  abre um OVA       ──fetch HTML──►  Apache /html/ovas/<arquivo>.html
   │                                      └─ React faz o parse e renderiza NATIVO
   │  lê / rola         ──────────────►  POST /progress/ova   (tempo + scroll)
   │  vídeo/podcast     ──────────────►  POST /progress/resource
   │  quiz              ──────────────►  POST /question/answer (correção no servidor)
   │  chat do OVA       ──────────────►  POST /edubot/tutor-chat (assistente da IA)
   ▼
Dashboard reflete consumo, competências e recomendações
```

---

## 2. Como subir a plataforma

Pré-requisito: **Docker** rodando.

```bash
cd EduBot
docker compose up --build -d
```

Verifique se os serviços subiram:

```bash
docker compose ps
```

Esperado: `ova_db`, `ova_back_end` e `ova_front_end` em **running**; o
`ova_react_build` aparece como **exited (0)** — isso é normal, ele só compila o
React e encerra.

Parar tudo:

```bash
docker compose down
```

### Credenciais de teste

| Campo | Valor |
|-------|-------|
| **RA** | `1` |
| **Senha** | `1` |

(O banco de exemplo tem 500 alunos — RA `1` a `500`, senha = o próprio RA. O RA
`4` é administrador.)

---

## 3. Mapa das telas (barra lateral)

| Item | O que mostra |
|------|--------------|
| **Dashboard** | Visão geral do aluno (consumo, progresso, atalhos) |
| **Conteúdos** | Lista de OVAs do aluno → **abre o leitor de OVA nativo** |
| **Atividades** | Atividades práticas |
| **Quiz** | Quiz por OVA (correção no servidor) |
| **Reforço** | OVA personalizada de reforço (agente de tool-use do EduBot) |
| **Meu Desempenho** | Gráficos de competências/evolução |
| **Tutor IA** | Recomendação **geral** do EduBot baseada no desempenho (≠ assistente do OVA) |

> ⚠️ **Não confundir:** a aba **"Tutor IA"** da barra lateral é a *recomendação
> geral* do EduBot. O **chat sobre o conteúdo** que você lê fica **dentro do
> próprio OVA** (lateral direita) — explicado na seção 5.

---

## 4. Funcionalidade: Leitor de OVA nativo

### Como funciona

Antes, "Abrir conteúdo" abria um **leitor legado** (Bootstrap/jQuery dentro de um
`iframe`, em outra aba). Agora o conteúdo é exibido **dentro do dashboard**, com a
mesma identidade visual do app:

- O React **busca o HTML do OVA** (`/html/ovas/<arquivo>.html`, servido pelo
  Apache — continua sendo a **fonte única de verdade** do conteúdo) e o **converte
  em componentes nativos**: títulos, parágrafos, imagens, **carrosséis** e
  **acordeões** em React (estado em hooks, sem jQuery).
- **Rastreio de leitura** (tempo de estudo + % de rolagem) é registrado
  automaticamente em `POST /progress/ova` — exatamente como o leitor legado fazia.
- **Mídias** do banco (vídeo/podcast/atividade) são renderizadas com os players
  React (`VideoPlayer`/`AudioPlayer`), com consumo persistido.
- **Quiz** embutido ao final, **corrigido no servidor** (o gabarito nunca chega ao
  navegador).

**Arquivos principais:**
`Front-End/react-logic-demo/src/services/ovaContent.ts` (fetch + parse) e
`Front-End/react-logic-demo/src/components/ova/OvaReader.tsx` (renderização +
rastreio + mídias + quiz), com `Carousel.tsx`, `Accordion.tsx` e `OvaQuiz.tsx`.

---

## 5. Funcionalidade: Assistente de IA por OVA

### Como funciona

Dentro da página do OVA existe um **chat lateral** com o qual o aluno conversa
sobre **o que está lendo naquele momento**:

- Em telas largas, ele **já aparece aberto na lateral direita** ao abrir o OVA.
- Pode ser recolhido (botão **"Ocultar assistente"**); quando recolhido, fica uma
  **aba fixa na borda direita — "Pergunte à IA"** — para reabrir a qualquer hora.
- O assistente responde **estritamente sobre o conteúdo do OVA** (grounding): o
  texto extraído do OVA é enviado como contexto. Se a pergunta fugir do tema, ele
  avisa que está fora do escopo e sugere tópicos daquele OVA.

### Sobre a IA (importante)

Seguindo a convenção do projeto, o **"cérebro" (a LLM) está MOCKADO**: o backend
devolve respostas no **mesmo formato da Anthropic Messages API** que o Claude
(via Bedrock/Anthropic) devolveria, usando recuperação determinística sobre o
material do OVA. **Ligar a LLM real** = trocar o cliente em
`Back-End/edubot/agent/tutor.py` (há um esqueleto comentado de Anthropic e de
Bedrock no fim do arquivo). O prompt, o contexto, a rota e o parsing **já são os
definitivos**.

**Arquivos principais:**
`Back-End/edubot/agent/tutor.py` (tutor mockado + esqueleto real),
rota `POST /edubot/tutor-chat` em `Back-End/edubot/api/routes/edubotRoute.py`,
UI em `Front-End/react-logic-demo/src/components/ova/TutorChat.tsx`.

---

## 6. Passo a passo de teste

### ✅ Teste A — Login e dashboard

1. Acesse http://localhost:8010/app/
2. Faça login com **RA `1` / senha `1`**.
3. Esperado: o **Dashboard** carrega com o nome do aluno na barra lateral e os
   indicadores de consumo no topo.

### ✅ Teste B — Leitor de OVA nativo

1. Na barra lateral, clique em **Conteúdos**.
2. Selecione um OVA na lista à esquerda (ex.: **Computação Quântica**) e clique em
   **Abrir conteúdo**.
3. Esperado:
   - O OVA abre **dentro do dashboard** (sem nova aba), com **hero**, **seções**,
     **imagens**, **carrosséis** e **acordeões** no estilo do app.
   - **Carrossel:** clique nas setas/bolinhas → o slide muda.
   - **Acordeão:** clique num item → expande/colapsa (um por vez).
   - **Barra de progresso** no topo avança conforme você **rola** a página.
4. Role até o fim → seção **"Teste seus conhecimentos"** (quiz).

### ✅ Teste C — Quiz (correção no servidor)

1. No fim do OVA (ou na aba **Quiz**), responda às questões.
2. Clique em **Verificar respostas**.
3. Esperado: cada questão fica **verde (correta)** ou **vermelha (incorreta)** —
   a correção vem do backend (`POST /question/answer`), o gabarito não fica no
   navegador. As tentativas alimentam o EduBot.

### ✅ Teste D — Assistente de IA do OVA (o foco)

1. Com um OVA aberto, observe o **chat na lateral direita** (em tela larga ele já
   vem aberto; se estiver recolhido, clique na aba **"Pergunte à IA"** na borda
   direita ou no botão **"Tirar dúvidas com a IA"** no topo).
2. **Pergunta no tema** — digite algo sobre o conteúdo, ex.:
   - *"Explique a superposição com outras palavras"*
   - *"O que é decoerência?"*
   - Ou use uma das **sugestões** exibidas.
   - Esperado: o assistente responde **citando o material do próprio OVA**.
3. **Pergunta fora do tema** — digite algo sem relação, ex.:
   - *"Qual a capital da França?"*
   - Esperado: ele responde que a pergunta está **fora do escopo do OVA** e
     sugere tópicos daquele conteúdo.
4. **Recolher/expandir** — clique em **"Ocultar assistente"**; a aba lateral
   **"Pergunte à IA"** aparece na borda; clique nela para reabrir.

### ✅ Teste E — Rastreio refletido no dashboard

1. Depois de ler um OVA (rolar boa parte) e/ou consumir mídias, clique em
   **Voltar** (seta no topo do OVA) ou troque de aba.
2. Vá ao **Dashboard** / **Meu Desempenho**.
3. Esperado: o **% consumido** e o progresso do OVA refletem a leitura (o
   rastreio é salvo em `/progress/ova` e `/progress/resource`).

### ✅ Teste F — Reforço (agente de tool-use) e Tutor IA geral

1. **Reforço:** aba **Reforço** → gera uma OVA personalizada com base na
   competência mais fraca (agente EduBot de tool-use).
2. **Tutor IA (geral):** aba **Tutor IA** → recomendação do EduBot baseada no
   perfil/desempenho (≠ chat do OVA).

---

## 7. Endpoints relevantes

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/login` | — | Autentica e devolve token Bearer |
| GET | `/student/me` | ✔ | Perfil completo do aluno logado |
| GET | `/ova/<id>/resources` | ✔ | Recursos (mídias) do OVA + progresso |
| POST | `/progress/ova` | ✔ | Salva tempo de leitura + % de scroll |
| POST | `/progress/resource` | ✔ | Salva consumo de vídeo/podcast/atividade |
| POST | `/question/ova` | ✔ | Questões do quiz (sem gabarito) |
| POST | `/question/answer` | ✔ | Corrige a resposta no servidor |
| **POST** | **`/edubot/tutor-chat`** | ✔ | **Assistente de IA do OVA (grounding no conteúdo)** |
| GET | `/edubot/recommendation` | ✔ | Recomendação geral do EduBot |
| POST | `/edubot/personalized-ova` | ✔ | Agente de tool-use → OVA de reforço |

### Exemplo: chamar o assistente do OVA via cURL

```bash
# 1) login -> token
TOKEN=$(curl -s http://localhost:5010/login \
  -H "Content-Type: application/json" \
  -d '[{"ra":"1","password":"1"}]' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

# 2) perguntar ao assistente (grounding no contexto enviado)
curl -s http://localhost:5010/edubot/tutor-chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '[{"ova_id":1,"context":"# Computacao Quantica\n## Superposicao\nUm qubit pode estar em 0 e 1 ao mesmo tempo.","messages":[{"role":"user","content":"O que e superposicao?"}]}]'
```

> No app, o campo `context` é montado automaticamente pelo front a partir do
> texto real do OVA (ver `ovaContextText` em `services/ovaContent.ts`).

---

## 8. Como ligar a IA real (opcional)

Hoje o assistente é **mockado**. Para usar o Claude de verdade:

1. Abra `Back-End/edubot/agent/tutor.py`.
2. No fim do arquivo há o esqueleto comentado `_AnthropicTutorClient` (API
   Anthropic) e a nota para Bedrock. Descomente o cliente desejado e troque a
   linha `_client = _MockTutorClient()` por ele.
3. Defina a credencial no ambiente do container `ova_back_end`
   (`ANTHROPIC_API_KEY`, ou credenciais AWS para Bedrock).
4. `docker compose up -d --build ova_flask`.

Nada mais muda: o `context` (material do OVA) já vai no *system prompt*, então o
tutor real também fica preso ao conteúdo do OVA.

---

## 9. Problemas comuns

| Sintoma | Causa provável / solução |
|---------|--------------------------|
| O app não reflete as últimas mudanças | Faça **Ctrl+F5** (assets têm hash novo, mas o `index.html` pode estar em cache). |
| "Conflict. The container name … is already in use" | Containers de uma execução anterior. `docker compose down` e suba de novo. |
| OVA abre vazio / sem conteúdo | O Apache precisa servir `/html/ovas/<arquivo>.html`. Confirme que `ova_front_end` está **running**. |
| Chat responde "fora do escopo" sempre | A pergunta realmente não bate com o material, ou o OVA não tem texto suficiente. Pergunte sobre um tópico citado nas seções. |
| Mudou o React e não atualizou | Recompile: `docker compose up -d --force-recreate ova_react_build ova_apache`. |

---

## Roteiro de 5 min — o Companheiro de Estudo (Plano 3)

O avatar deixou de ser recompensa e virou um **companheiro que estuda com você**.
Roteiro rápido para demonstrar (login aluno RA `1` / senha `1`):

1. **Escolha a persona** (30s): abra **Meu Desempenho** → no card do coach, troque o
   avatar para **Einstein** ou **Curie** (sem cadeados — livres para todos). A escolha
   é salva no servidor (segue entre dispositivos) e muda o avatar 3D + a voz.
2. **Abra um módulo** (1min): **Conteúdos** → abra um OVA. O personagem aparece no
   canto inferior-esquerdo e **saúda** (retomando de onde você parou, se já leu antes).
   Role a página: ele comenta aos **50%** e ao **concluir**.
3. **Ouça o conteúdo** (1min): em qualquer seção, clique **🔊 Ouvir** — o personagem
   lê o texto em voz alta (voz da persona; a boca anima). Clique **✨ Explique** para
   mandar a seção ao tutor.
4. **O tutor É o personagem** (1min): o painel lateral tem o avatar e o nome da
   persona ("Prof. Einstein"), cada resposta tem **▶ ouvir**. Feche e reabra o painel:
   a conversa **não se perde**.
5. **Erre o quiz de propósito** (1min): ao final, responda uma questão errada — o
   companheiro oferece **"Explicar"** (abre o tutor com a pergunta pronta); acerte e
   ele comemora com o **+XP**.
6. **Visão do tutor** (30s): entre como tutor (RA `2` / senha `2`) → **Painel do
   Tutor** → card **"Companheiro de estudo"**: quantos alunos usaram, seções ouvidas,
   explicações e falas ouvidas na semana.

> Desligar tudo: `EDUBOT_COMPANION=off` no `.env` devolve o leitor idêntico ao
> anterior. A voz real (AWS Polly) exige credencial própria; sem ela, o companheiro
> usa a voz do navegador (Web Speech) — funciona igual.

---

*Última atualização: 2026-07-19.*
