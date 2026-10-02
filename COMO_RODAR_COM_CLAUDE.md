# Como instalar e rodar o EduBot — guia para quem usa o Claude Code

Guia de partida para alguém que recebeu este projeto e também trabalha com o
**Claude Code**. Objetivo: sair do zero até a plataforma no ar, com o Claude Code
podendo dirigir o processo. Você **não precisa saber Python nem React** — quem
sobe tudo é o Docker.

> **TL;DR:** instale Docker Desktop + Git, clone o repositório, e rode
> `docker compose up -d --build` na pasta `EduBot/`. Abra
> **http://localhost:8010/app/** e entre com RA `1` / senha `1`.
> A IA vem em **modo mock** por padrão — não precisa de nenhuma chave nem gasta nada.

---

## 0. O que você vai instalar

| Ferramenta | Obrigatório? | Para quê |
|---|---|---|
| **Docker Desktop** | ✅ Sim | Sobe o banco, o backend e o frontend em containers. É o único requisito de verdade para rodar. |
| **Git** | ✅ Sim | Baixar o código e versionar. |
| **Claude Code** | ⭐ Recomendado | O "piloto": abre a pasta, roda os comandos, testa e edita o projeto por você. |
| **Node.js 20+** | ⛔ Opcional | Só se for **desenvolver o frontend** com hot-reload. O `docker compose` já compila o React sozinho num container — sem Node na máquina. |

---

## 1. Instalar os pré-requisitos

### 1.1 Docker Desktop (obrigatório)

- **Windows / macOS:** baixe em https://www.docker.com/products/docker-desktop/ e instale.
- No Windows, o instalador ativa o **WSL 2** (aceite). Reinicie se ele pedir.
- Abra o Docker Desktop **uma vez** e espere o ícone ficar verde ("Engine running").
- Confirme no terminal:

```bash
docker --version
docker compose version
```

### 1.2 Git (obrigatório)

- **Windows:** https://git-scm.com/download/win (instala também o *Git Bash*).
- **macOS:** `xcode-select --install` ou `brew install git`.

```bash
git --version
```

### 1.3 Claude Code (recomendado)

O Claude Code é a CLI que deixa o Claude abrir esta pasta e executar tudo (subir a
stack, rodar os testes, editar código). Instale de um jeito:

**Windows (PowerShell):**
```powershell
irm https://claude.ai/install.ps1 | iex
```

**macOS / Linux:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Ou via npm (qualquer SO, precisa de Node 18+):**
```bash
npm install -g @anthropic-ai/claude-code
```

Depois, dentro da pasta do projeto, rode `claude` e faça login com `/login` na
primeira vez. Há extensões para **VS Code** e **JetBrains** também.

### 1.4 Node.js (opcional — só para dev do frontend)

Baixe a versão **LTS (20+)** em https://nodejs.org. Só necessário se você for rodar
`npm run dev` no React. Para **apenas usar/testar** a plataforma, pule.

---

## 2. Pegar o código

Se já recebeu a pasta `OVA-Rastreamento/EduBot`, pule para o passo 3. Para clonar:

```bash
git clone <URL-do-repositorio>
cd OVA-Rastreamento/EduBot
```

> ⚠️ A **raiz do repositório Git é a pasta `EduBot/`** (é onde ficam o `compose.yaml`
> e o `.git`). Rode todos os comandos de dentro dela. A pasta-mãe `OVA-Rastreamento/`
> e a irmã `OVA-IA/` **não** fazem parte do versionamento (`OVA-IA/` é uma cópia
> antiga usada só para material de apresentação).

---

## 3. Rodar a plataforma (caminho feliz)

Com o Docker Desktop aberto, na pasta `EduBot/`:

```bash
docker compose up -d --build
```

Isso sobe **3 serviços** (a primeira vez baixa imagens e compila o React — leva alguns minutos):

| Container | O que é | Porta (host) |
|---|---|---|
| `ova_db` | MySQL 8.4 (banco) | 3310 |
| `ova_back_end` | API Flask (Python) | 5010 |
| `ova_front_end` | Apache servindo o React já compilado | 8010 |
| `ova_react_build` | compila o frontend e **sai com código 0** (não fica no ar) | — |

Verifique se subiu:

```bash
docker compose ps          # espere ova_db como (healthy) e o back/front "Up"
```

**Abra no navegador:**

- 🎯 **Interface nova (React, recomendada):** http://localhost:8010/app/
- API (para curl/testes): http://localhost:5010

### 3.1 Credenciais de teste (seed)

O banco já nasce com dados de exemplo. **A senha é igual ao RA.**

| RA (login) | Senha | Perfil |
|---|---|---|
| `1` | `1` | Aluno |
| `2` | `2` | **Tutor / Professor** |
| `4` | `4` | **Admin / Gestor** |
| `3`, `5`, `6`, `7`… | igual ao RA | Alunos |

> No 1º login de cada aluno a senha é convertida para hash (upgrade-on-login) —
> normal. Rotas de professor/gestor (`#/tutor`, `#/gestor`) aparecem para RA `2` e `4`.

Pronto: a plataforma está rodando **sem IA real, sem custo e sem credencial nenhuma**.

---

## 4. Deixar o Claude Code fazer por você

Abra o Claude Code **dentro da pasta `EduBot/`**:

```bash
claude
```

Este repositório traz uma **skill de projeto chamada `run`** com o passo a passo de
subir e testar a stack de ponta a ponta (inclui o macete das migrations, as
credenciais e um driver de teste do front com Playwright). Basta pedir em linguagem
natural, por exemplo:

- *"rode o projeto para eu testar"*
- *"suba a stack e verifique se o login funciona"*
- *"os containers estão de pé? mostre o status"*

O Claude reconhece a skill `run` e executa os comandos por você. As instruções do
projeto (idioma português, nunca commitar `.env`, preservar o comportamento visual,
etc.) já vão junto no contexto.

---

## 5. Armadilhas comuns (leia antes de abrir chamado 😄)

### 5.1 "GET /student/me responde 500" ou o login quebra no 2º acesso
Você está reusando um **volume MySQL antigo**, e as *migrations* novas não rodaram
(o MySQL só executa os `.sql` na **primeira** inicialização do volume).

- **Solução limpa (recomendada — apaga os dados e recria do zero):**
  ```bash
  docker compose down -v && docker compose up -d --build
  ```
- **Sem apagar dados** (as migrations são idempotentes):
  ```bash
  for m in Database/sql/migration_*.sql; do
    docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db < "$m"
  done
  ```

### 5.2 "port is already allocated" / nome de container em conflito
Já existe uma stack no ar (outra cópia do projeto usando as mesmas portas/nomes
fixos `ova_db`/3310, `ova_back_end`/5010, `ova_front_end`/8010). Derrube a antiga na
pasta que a subiu:

```bash
docker ps --filter "name=ova_" --format "{{.Names}}\t{{.Status}}"
docker compose down     # rodado na pasta da stack existente
```

### 5.3 O container do React (`ova_react_build`) não deve ficar "rodando"
Ele **compila e sai com código 0** — isso é o esperado. Se ele sair com **erro**,
veja o log: `docker compose logs ova_react_build`.

### 5.4 IA real (opcional) — e o `.env`
A IA vem **mockada** por padrão (determinística, de graça). Para ligar o Claude real
via **AWS Bedrock**, crie um arquivo **`.env` na raiz `EduBot/`** a partir do
`.env.example` (veja também [IA_AWS_SETUP.md](IA_AWS_SETUP.md)). O `compose.yaml`
carrega o `.env` sozinho.

> 🔒 **Nunca comite o `.env`.** Ele já está no `.gitignore` e pode conter credenciais.
> Sem `.env`, tudo continua funcionando em modo mock.

---

## 6. Parar, reiniciar e limpar

```bash
docker compose stop            # pausa (mantém os dados)
docker compose up -d           # religa
docker compose down            # remove os containers (mantém o volume/dados)
docker compose down -v         # remove TAMBÉM o volume do MySQL (zera o banco)
docker compose logs -f ova_back_end   # acompanhar o log do backend
```

---

## 7. Rodar só o backend, sem Docker (opcional)

Útil para debugar a API rápido, em SQLite na memória:

```powershell
cd Back-End
pip install -r requirements.txt
python tools/init_test_db.py   # cria dev_ova.db (SQLite) com dados de exemplo
python api/api.py              # API em http://127.0.0.1:8090 (login RA 1 / senha 1)
```

---

## 8. Rodar os testes

```bash
cd Back-End && python -m pytest      # testes em SQLite na memória, sem Docker
```

---

## 9. Mapa da documentação

| Quer… | Leia |
|---|---|
| Entender e testar tudo passo a passo | [COMO_TESTAR_PLATAFORMA.md](COMO_TESTAR_PLATAFORMA.md) |
| Ligar a IA real (AWS Bedrock) | [IA_AWS_SETUP.md](IA_AWS_SETUP.md) |
| Ver o fluxo/arquitetura em diagrama | [docs/plataforma-fluxo.html](docs/plataforma-fluxo.html) |
| Adicionar conteúdo (OVAs, vídeos, quiz) | [COMO_ADICIONAR_CONTEUDO.md](COMO_ADICIONAR_CONTEUDO.md) |
| Abrir/desenvolver o frontend novo | [COMO_ABRIR_FRONTEND_NOVO.md](COMO_ABRIR_FRONTEND_NOVO.md) |
| Arquitetura e funcionamento completos | [ARQUITETURA_EDUBOT.md](ARQUITETURA_EDUBOT.md) |
| Visão geral do projeto | [README.md](README.md) |
