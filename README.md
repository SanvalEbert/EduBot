# EduBot

Plataforma de aprendizagem que **mede o que o aluno realmente faz** num Objeto
Virtual de Aprendizagem (OVA), **estima o domínio dele por competência** e **age
sozinha** — recomenda ao aluno, monta trilhas de reforço e avisa o professor
antes de o aluno ficar para trás.

Extensão do projeto `OVA-Rastreamento`. Visão completa em
[ARQUITETURA_EDUBOT.md](ARQUITETURA_EDUBOT.md).

## Como rodar

```bash
git clone https://github.com/VictorBarretoAndrade/EduBot.git
cd EduBot
docker compose up -d --build
```

- Interface (React): <http://localhost:8010/app/> — login do seed: RA = senha (`1`/`1` aluno, `2`/`2` tutor)
- API (Flask): <http://localhost:5010>
- MySQL: porta `3310`

O frontend é compilado por um container Node durante o `up` — não é preciso ter
Node na máquina. A IA vem em **modo mock** por padrão (sem chave, sem custo);
para ligar o Claude real, veja [IA_AWS_SETUP.md](IA_AWS_SETUP.md).

> Em um volume MySQL **já existente**, as migrations não rodam sozinhas (o init
> só executa em volume novo). Aplique à mão:
> `docker exec -i ova_db mysql -ueduardo -pPassword-1 ova_db < Database/sql/migration_0XX_*.sql`

Testes do backend: `cd Back-End && python -m pytest`.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| [Back-End/](Back-End/) | API Flask — pacote `edubot/` (`api/`, `services/`, `agent/`, `data/`), testes em `tests/` |
| [Front-End/](Front-End/) | SPA React em `react-logic-demo/`; HTML estático dos OVAs em `files/` |
| [Database/](Database/) | DDL, seed e migrations do MySQL |
| [integracoes/](integracoes/) | Clientes prontos (JS e PHP) da API pública para parceiros |
| [compose.yaml](compose.yaml) | Os 4 serviços: MySQL, Flask, build do React, Apache |

## Documentação

| Quer… | Leia |
|---|---|
| Entender o sistema inteiro | [ARQUITETURA_EDUBOT.md](ARQUITETURA_EDUBOT.md) |
| Entender as regras e a jornada do aluno, sem jargão | [REGRAS_DE_NEGOCIO_E_FLUXO_DO_ALUNO.md](REGRAS_DE_NEGOCIO_E_FLUXO_DO_ALUNO.md) |
| Ver a jornada do aluno em um diagrama | [FLUXOGRAMA_CAMINHO_DO_ALUNO.md](FLUXOGRAMA_CAMINHO_DO_ALUNO.md) |
| Entender como o rastreio funciona | [COMO_O_RASTREIO_FUNCIONA.md](COMO_O_RASTREIO_FUNCIONA.md) |
| Integrar um sistema externo à API | [INTEGRACAO_API_EXTERNA.md](INTEGRACAO_API_EXTERNA.md) |
| Subir a plataforma do zero | [COMO_RODAR_COM_CLAUDE.md](COMO_RODAR_COM_CLAUDE.md) |
| Abrir e desenvolver o frontend | [COMO_ABRIR_FRONTEND_NOVO.md](COMO_ABRIR_FRONTEND_NOVO.md) |
| Testar cada funcionalidade | [COMO_TESTAR_PLATAFORMA.md](COMO_TESTAR_PLATAFORMA.md) |
| Cadastrar conteúdo (OVAs, vídeos, quiz) | [COMO_ADICIONAR_CONTEUDO.md](COMO_ADICIONAR_CONTEUDO.md) |
| Ligar a IA real (AWS Bedrock) | [IA_AWS_SETUP.md](IA_AWS_SETUP.md) |
| Entender o avatar 3D e as personas | [AVATAR_3D.md](AVATAR_3D.md) |
| Demonstrar a plataforma ao vivo | [ROTEIRO_APRESENTACAO.md](ROTEIRO_APRESENTACAO.md) |

## Teste local sem Docker

Onde nao ha' acesso ao socket do Docker (usuario fora do grupo `docker`), o
`run-local.sh` sobe a mesma stack — API Flask + frontend React — com SQLite no
lugar do MySQL e um servidor estatico no lugar do Apache:

```bash
./run-local.sh              # sobe tudo; instala venv, Node e deps na 1a vez
./run-local.sh --rebuild    # forca npm install + build do React
./run-local.sh --reset-db   # apaga o SQLite e semeia de novo
```

- Frontend: <http://localhost:8010/app/> — login RA `1` / senha `1`
- API: <http://localhost:8090>
- Portas ajustaveis por `API_PORT` / `WEB_PORT`.

O Node e' baixado em `.tooling/` quando o sistema nao tem um >= 18 (sem sudo).
**Atencao:** o schema vem dos models via peewee, entao as migrations SQL de
`Database/sql/` **nao** sao exercitadas neste modo — para valida-las, use o
Docker/MySQL.

Para subir so' a API, na mao:

```bash
python3 -m venv .venv && .venv/bin/pip install -r Back-End/requirements.txt
cd Back-End
export EDUBOT_DB=sqlite
../.venv/bin/python tools/init_test_db.py   # cria dev_ova.db com dados de exemplo
../.venv/bin/python -m edubot.api.app       # API em http://127.0.0.1:8090
```

