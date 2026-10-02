#!/usr/bin/env bash
#
# Sobe o EduBot inteiro NESTA máquina, sem Docker.
#
# Porque existe: o caminho oficial e' `docker compose up --build`, mas ele exige
# acesso ao socket do Docker (grupo `docker`). Onde esse acesso nao existe, este
# script entrega a mesma stack — API Flask + frontend React — usando SQLite no
# lugar do MySQL e um servidor estatico no lugar do Apache.
#
#   ./run-local.sh            sobe tudo (instala o que faltar na primeira vez)
#   ./run-local.sh --rebuild  forca npm install + build do React de novo
#   ./run-local.sh --reset-db apaga o SQLite e semeia de novo
#
# Diferencas em relacao ao compose, de proposito:
#   - Banco: SQLite (EDUBOT_DB=sqlite), nao MySQL. As 22 migrations SQL do
#     Database/ NAO rodam aqui; o schema vem dos models via peewee
#     (tools/init_test_db.py). Serve para desenvolver e demonstrar, nao para
#     validar as migrations.
#   - Voz: EDUBOT_SPEECH=off. O padrao "auto" tenta o AWS Polly, e sem
#     credencial isso so' gasta timeout antes de cair no Web Speech do browser.
#   - Scheduler: desligado, para o log ficar legivel.
# Ajuste qualquer um deles exportando a variavel antes de chamar o script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8090}"
WEB_PORT="${WEB_PORT:-8010}"
NODE_VERSION="${NODE_VERSION:-20.18.1}"

VENV="$ROOT/.venv"
TOOLING="$ROOT/.tooling"
DB_PATH="${EDUBOT_SQLITE_PATH:-$ROOT/Back-End/dev_ova.db}"
WEB_ROOT="$ROOT/Front-End/files"
APP_DIR="$WEB_ROOT/app"

REBUILD=0
RESET_DB=0
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    --reset-db) RESET_DB=1 ;;
    -h|--help) sed -n '3,23p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "argumento desconhecido: $arg (use --help)" >&2; exit 2 ;;
  esac
done

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*" >&2; exit 1; }

port_busy() {
  # -H omite o cabecalho; sem ele o grep casaria com a linha de titulo.
  ss -ltnH 2>/dev/null | grep -q ":$1 "
}

for p in "$API_PORT" "$WEB_PORT"; do
  port_busy "$p" && die "porta $p ja' esta' em uso. Libere-a ou rode com API_PORT/WEB_PORT diferentes."
done

# ---------------------------------------------------------------- Python
if [ ! -x "$VENV/bin/python" ]; then
  say "Criando venv em .venv"
  python3 -m venv "$VENV"
  # Marca ausente forca o pip install abaixo.
fi

# requirements.txt mais novo que o stamp => dependencia nova entrou no arquivo.
STAMP="$VENV/.requirements-stamp"
if [ ! -f "$STAMP" ] || [ "$ROOT/Back-End/requirements.txt" -nt "$STAMP" ]; then
  say "Instalando dependencias Python"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r "$ROOT/Back-End/requirements.txt"
  touch "$STAMP"
fi

# ---------------------------------------------------------------- Node
# O compose compila o React num container node:20-alpine. Sem Docker, usamos o
# Node do sistema quando ele serve, e senao baixamos o tarball oficial para
# .tooling/ — sem sudo, sem tocar no sistema.
node_ok() {
  command -v node >/dev/null 2>&1 || return 1
  local major
  major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)" || return 1
  [ "$major" -ge 18 ]
}

if [ -x "$TOOLING/node/bin/node" ]; then
  export PATH="$TOOLING/node/bin:$PATH"
elif ! node_ok; then
  say "Node >= 18 nao encontrado; baixando Node $NODE_VERSION em .tooling/"
  mkdir -p "$TOOLING/node"
  tarball="node-v$NODE_VERSION-linux-x64.tar.xz"
  curl -fsSL -o "$TOOLING/$tarball" "https://nodejs.org/dist/v$NODE_VERSION/$tarball" \
    || die "falha ao baixar o Node. Sem rede? Instale o Node >= 18 manualmente."
  tar xf "$TOOLING/$tarball" -C "$TOOLING/node" --strip-components=1
  rm -f "$TOOLING/$tarball"
  export PATH="$TOOLING/node/bin:$PATH"
fi
node_ok || die "Node continua indisponivel."

# ---------------------------------------------------------------- Banco
export EDUBOT_DB=sqlite
export EDUBOT_SQLITE_PATH="$DB_PATH"

if [ "$RESET_DB" = 1 ]; then
  say "Apagando o banco ($DB_PATH)"
  rm -f "$DB_PATH"
fi

if [ ! -f "$DB_PATH" ]; then
  say "Semeando o SQLite (aluno de teste: RA 1 / senha 1)"
  ( cd "$ROOT/Back-End" && "$VENV/bin/python" tools/init_test_db.py )
fi

# ---------------------------------------------------------------- Frontend
FRONT="$ROOT/Front-End/react-logic-demo"

if [ "$REBUILD" = 1 ] || [ ! -d "$FRONT/node_modules" ]; then
  say "npm install (pode demorar na primeira vez)"
  ( cd "$FRONT" && npm install --no-fund --no-audit )
fi

if [ "$REBUILD" = 1 ] || [ ! -f "$APP_DIR/index.html" ]; then
  say "Compilando o React em Front-End/files/app"
  # VITE_API_URL: o default embutido no app e' :5010, a porta que o compose
  # publica. Fora do Docker o Flask fala direto na API_PORT, entao o valor tem
  # de ser injetado no build — nao ha' como corrigir depois, ja' que o Vite
  # inlineia isso no bundle.
  ( cd "$FRONT" \
    && VITE_OUT_DIR="$APP_DIR" \
       VITE_API_URL="http://localhost:$API_PORT" \
       VITE_CLASSIC_URL="http://localhost:$WEB_PORT" \
       npm run build )
fi

# ---------------------------------------------------------------- Runtime
export EDUBOT_SECRET="${EDUBOT_SECRET:-dev-secret-change-me}"
export EDUBOT_CORS_ORIGINS="${EDUBOT_CORS_ORIGINS:-http://localhost:$WEB_PORT}"
export EDUBOT_DEBUG="${EDUBOT_DEBUG:-0}"
export EDUBOT_SCHEDULER="${EDUBOT_SCHEDULER:-off}"
export EDUBOT_SPEECH="${EDUBOT_SPEECH:-off}"
export EDUBOT_LLM_PROVIDER="${EDUBOT_LLM_PROVIDER:-mock}"

PIDS=()
cleanup() {
  trap - EXIT INT TERM
  say "Encerrando"
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

say "API Flask em http://localhost:$API_PORT"
( cd "$ROOT/Back-End" && exec "$VENV/bin/python" -m edubot.api.app ) &
PIDS+=("$!")

say "Frontend em http://localhost:$WEB_PORT/app/"
( cd "$WEB_ROOT" && exec python3 -m http.server "$WEB_PORT" --bind 127.0.0.1 ) &
PIDS+=("$!")

# Espera a API responder antes de declarar que subiu: um traceback no import
# mataria o processo em silencio e o usuario ficaria olhando uma URL morta.
ready=0
for _ in $(seq 1 30); do
  sleep 1
  if curl -fsS -o /dev/null -X POST "http://127.0.0.1:$API_PORT/login" \
       -H 'Content-Type: application/json' -d '{"ra":"1","password":"1"}'; then
    ready=1
    break
  fi
  # Um dos dois filhos morreu => aborta em vez de esperar o timeout inteiro.
  for pid in "${PIDS[@]}"; do
    kill -0 "$pid" 2>/dev/null || die "um dos servicos caiu no boot (veja o log acima)."
  done
done
[ "$ready" = 1 ] || die "a API nao respondeu em 30s. Veja o log acima."

cat <<INFO

  Abra:   http://localhost:$WEB_PORT/app/
  Login:  RA 1  /  senha 1
  API:    http://localhost:$API_PORT
  Banco:  $DB_PATH  (SQLite)
  IA:     EDUBOT_LLM_PROVIDER=$EDUBOT_LLM_PROVIDER

  Ctrl+C encerra os dois servicos.

INFO

# wait -n (nao `wait`) retorna no PRIMEIRO filho que morrer. Com `wait`, a API
# podia cair no meio da sessao e o script seguia vivo servindo um frontend sem
# backend; agora a morte de qualquer um dos dois dispara o cleanup dos dois.
wait -n
