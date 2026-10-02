# Como abrir o EduBot (frontend React)

Guia rápido para abrir a plataforma **EduBot** (React + Vite + Tailwind), onde ficam
as abas **Conteúdos**, **Quiz**, **Reforço** (OVA personalizada gerada pelo agente),
**Meu Desempenho** (competências, gamificação, coach com avatares) e o **Painel do
Tutor** (para tutor/admin).

> **O frontend clássico (jQuery: `login.html`, `painel.html`, `plots.html`) foi
> APOSENTADO** (Fase 5 / A17). Hoje existe **um app React único** servido em `/app/`.
> A raiz `/` apenas redireciona para lá. Aluno, tutor e admin usam o mesmo app — o
> que muda é o que cada papel enxerga (o tutor/admin ganha o **Painel do Tutor**
> dentro do próprio app).

---

## Opção A — Docker (recomendada, **não precisa de Node**)

Esta é a forma normal de usar. Um container (`ova_react_build`) compila o React
automaticamente durante o `up` e o Apache serve o resultado — você não precisa
ter Node/npm instalado na máquina.

**Pré-requisito:** Docker Desktop instalado e rodando.

```powershell
cd EduBot          # pasta que contém o compose.yaml (é a raiz do repositório)
docker compose up -d --build
```

Aguarde os containers subirem. Sinais de sucesso:

- `ova_db` fica **healthy**;
- `ova_react_build` termina com **exit 0** (ele compila e sai — é o esperado);
- `ova_back_end` e `ova_front_end` ficam **up**.

Depois abra no navegador:

- **EduBot:** http://localhost:8010/app/  (a raiz http://localhost:8010/ redireciona para cá)

### Login (senha = RA)

| Perfil | RA (usuário) | Senha |
|--------|----|-------|
| Aluno  | 1  | 1     |
| Tutor  | 2  | 2     |
| Admin (coordenador) | 4 | 4 |

> O aluno (RA `1`) vê Conteúdos/Quiz/Reforço/Meu Desempenho. **Tutor (RA `2`)** e
> **admin (RA `4`)** veem também o **Painel do Tutor** (KPIs do agente, fila de
> aprovação, heatmap de domínio, engajamento) na barra lateral.

### Onde está a feature de Reforço

Depois de logar, clique em **"Reforço"** na barra lateral → **"Gerar OVA de
reforço"**. O agente diagnostica o assunto em que você foi pior e monta uma trilha
(vídeos, textos e questões). As OVAs geradas ficam listadas ali; clique em
**"Abrir"** para consumir.

> Para o agente ter o que recomendar, é preciso ter conteúdo cadastrado com
> `competency_id` (veja [COMO_ADICIONAR_CONTEUDO.md](COMO_ADICIONAR_CONTEUDO.md)) e
> algum desempenho registrado (ex.: errar questões do quiz daquele assunto).

### Parar

```powershell
docker compose down       # para os containers, PRESERVA o banco
docker compose down -v    # para e APAGA o volume do banco (reset total)
```

> **Migrations (gotcha importante):** em **volume novo** (primeira vez ou após
> `down -v`), o MySQL roda sozinho ddl → dml → **migrations 001…018** em ordem.
> Reusando um **volume antigo**, as migrations novas **não** rodam
> automaticamente — sintoma típico: `GET /student/me` responde 500. Aplique-as (são
> idempotentes):
> ```powershell
> Get-ChildItem Database/sql/migration_*.sql | Sort-Object Name | ForEach-Object {
>   Get-Content $_.FullName | docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db
> }
> ```

---

## Opção B — Desenvolvimento com hot-reload (precisa de Node)

Use só se for **mexer no código** do React e quiser recarregamento automático.

**Pré-requisito:** Node.js 20+ instalado **e o backend no ar** (o app fala com a
API em `http://<host>:5010` — suba o backend via `docker compose up -d`, que expõe
essa porta).

```powershell
cd Front-End/react-logic-demo
npm install
npm run dev
```

O Vite sobe em **http://127.0.0.1:5173/**. Abra esse endereço — o app recarrega
sozinho a cada alteração.

> Em dev, o app continua chamando a API na porta **5010**; os valores padrão ficam
> em `src/services/config.ts` e podem ser sobrescritos por variáveis de ambiente
> (`VITE_API_URL` / `VITE_CLASSIC_URL`). Por isso o backend (container) precisa
> estar rodando em paralelo; só o `npm run dev` não basta.

Scripts (em `package.json`):

| Comando | O que faz |
|---------|-----------|
| `npm run dev` | Servidor de desenvolvimento (hot-reload) em `127.0.0.1:5173` |
| `npm run build` | Type-check (`tsc`) + build de produção do Vite |
| `npm run preview` | Serve localmente o build de produção para conferência |

> **Atenção:** o type-check "de verdade" é o `npm run build` (`tsc && vite build`),
> que é exatamente o que o container `ova_react_build` roda. Um `npx tsc` avulso no
> host pode usar a ferramenta errada — prefira `npm run build`.

---

## Demonstrar do zero (consentimento + tutorial)

O **modal de consentimento (LGPD)** e o **tutorial do EduBot** aparecem no 1º acesso e
são controlados por flags no **localStorage** do navegador (`edubot.consent.v1` e
`edubot.onboarding.v1`), lidas só no carregamento da página.

- Jeito mais limpo para demo: abra em **janela anônima** (`Ctrl+Shift+N`) →
  login → consentimento → tutorial, na sequência natural.
- Já logado, para reexibir sem perder a sessão, no Console (`F12`):
  ```js
  localStorage.removeItem("edubot.consent.v1");
  localStorage.removeItem("edubot.onboarding.v1");
  location.reload();
  ```
- Para zerar também os **dados do servidor** (XP, consentimentos, tentativas):
  `docker compose down -v` e suba de novo.

---

## Solução de problemas

| Sintoma | Provável causa / o que fazer |
|---------|------------------------------|
| Página em branco em `/app/` | O build do React ainda não terminou — aguarde o serviço `ova_react_build` sair com **exit 0**, ou rode com `--build`. |
| "Não foi possível carregar seus dados" / volta para o login | Backend (Flask, porta 5010) fora do ar, **ou** token expirado. Confira o container do backend e faça login de novo. |
| `GET /student/me` responde 500 | Volume MySQL antigo sem as migrations novas — aplique os `migration_*.sql` (ver nota na Opção A). |
| Aba **Reforço** diz que não há conteúdo | Falta conteúdo com `competency_id` para o assunto fraco, ou o aluno ainda não tem desempenho registrado. |
| Erro de tipo no build | Rode `npm run build` em `Front-End/react-logic-demo` para ver a mensagem do TypeScript; ajuste e rebuild. |

---

## Referências

- [README.md](README.md) — visão geral, endpoints, login e como cadastrar conteúdo.
- [COMO_TESTAR_PLATAFORMA.md](COMO_TESTAR_PLATAFORMA.md) — roteiro de teste ponta a ponta.
- [COMO_ADICIONAR_CONTEUDO.md](COMO_ADICIONAR_CONTEUDO.md) — cadastrar OVAs, vídeos e questões.
- [ARQUITETURA_EDUBOT.md](ARQUITETURA_EDUBOT.md) — arquitetura, dados do aluno e o agente EduBot.
