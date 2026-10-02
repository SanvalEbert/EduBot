"""Coleta de eventos de páginas de terceiros (`/api/v1/collect`).

É a contraparte do `integracoes/js/edubot-tracker.js`: um material HTML de fora
do EduBot inclui o script, que captura cliques e tempo de página e envia em lote
para cá. Os eventos vão para `collected_events` (migration_022), NÃO para
`learning_events` — ver a migration para o porquê.

    POST /api/v1/collect          grava um lote (chave com `events:write`)
    GET  /api/v1/collect/events   lê o que foi coletado (chave com `tracking:read`)

Diferenças deliberadas em relação ao resto da /api/v1:

  * CORS aberto. O script roda no navegador, em qualquer site (ou em file://,
    que manda `Origin: null`). `EDUBOT_COLLECT_ORIGINS` restringe, se preciso.
  * A chave pode vir no CORPO (`"key": ...`), não só no header. O envio feito
    quando a página fecha usa `navigator.sendBeacon`, que não aceita header
    customizado; e um POST `text/plain` sem header extra é "simple request",
    então nem gera preflight.
  * A chave é PÚBLICA (está no HTML). Por isso `events:write` só grava, e o
    apikey_tool recusa misturá-lo com escopos de leitura.

Contrato do POST (corpo JSON, Content-Type application/json OU text/plain):

    {
      "key": "ek_live_...",                 # ou header X-API-Key
      "visitor_id": "a1b2c3d4...",          # obrigatório, 8-64 [A-Za-z0-9_-]
      "session_id": "...",                  # opcional, mesmo formato
      "user_id": "...",                     # opcional, id externo (<= 64)
      "page_url": "...", "page_title": "...",
      "events": [
        {"type": "click", "target": "botao-teste",
         "context": {...}, "occurred_at": "2026-09-23T14:00:00.000Z"}
      ]
    }

Resposta: {"accepted": n, "errors": n, "rejected": [{"index": i, "reason": "..."}]}
Best-effort por item, como o POST /events do aluno: um item ruim não derruba o
lote; só vira 400 quando NADA do lote é aproveitável.
"""
import datetime
import json
import os
import re

from flask import Blueprint, request
from flask_cors import cross_origin
from peewee import PeeweeException

from edubot.api.apikey import (_extract_key, rate_limited, require_api_key,
                               resolve_key, touch_usage)
from edubot.api.routes.publicApiRoute import (_bad_request, _date_arg, _int_arg,
                                              _limit, _ok, _paged)
from edubot.data.models.collected_events import CollectedEvents
from edubot.services.events import _parse_dt

app_collect = Blueprint("collect", __name__, url_prefix="/api/v1")

MAX_BATCH = 50
MAX_BODY_BYTES = 64 * 1024
MAX_CONTEXT_BYTES = 2000
# Um material aberto pela turma inteira compartilha UMA chave: o teto precisa
# comportar N navegadores enviando lotes a cada poucos segundos.
COLLECT_RATE_LIMIT = int(os.environ.get("EDUBOT_COLLECT_RATE_LIMIT", "600"))

# Relógio do navegador não é confiável. Aceitamos o horário do cliente dentro
# desta janela (eventos enfileirados offline chegam atrasados); fora dela vale
# o horário de chegada.
_MAX_PAST = datetime.timedelta(days=7)
_MAX_FUTURE = datetime.timedelta(minutes=5)

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_TYPE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,40}$")

_origins_env = os.environ.get("EDUBOT_COLLECT_ORIGINS", "*").strip() or "*"
_ALLOWED_ORIGINS = "*" if _origins_env == "*" else \
    [o.strip() for o in _origins_env.split(",") if o.strip()]


def _error(message, status):
    return json.dumps({"error": message, "status": status}, ensure_ascii=False), status, \
        {"Content-Type": "application/json; charset=utf-8"}


def _read_body():
    """Corpo como dict, independente do Content-Type (o sendBeacon manda
    text/plain). Retorna None se não for um objeto JSON."""
    try:
        data = json.loads(request.get_data(as_text=True) or "null")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _clip(value, size):
    if value is None:
        return None
    text = str(value).strip()
    return text[:size] if text else None


def _occurred_at(raw, now):
    dt = _parse_dt(raw)
    if dt is None or dt < now - _MAX_PAST or dt > now + _MAX_FUTURE:
        return now
    return dt


def _validate_item(ev):
    """Retorna (campos, None) ou (None, motivo)."""
    if not isinstance(ev, dict):
        return None, "item não é objeto"
    event_type = ev.get("type")
    if not isinstance(event_type, str) or not _TYPE_RE.match(event_type):
        return None, "type ausente ou inválido (1-40 caracteres: letras, números, _ . : -)"
    context = ev.get("context")
    if context is not None:
        if not isinstance(context, dict):
            return None, "context deve ser objeto"
        if len(json.dumps(context, ensure_ascii=False)) > MAX_CONTEXT_BYTES:
            return None, f"context maior que {MAX_CONTEXT_BYTES} bytes"
    return {"event_type": event_type, "target": _clip(ev.get("target"), 120),
            "context": context or None, "occurred_at": ev.get("occurred_at")}, None


@app_collect.route("/collect", methods=["POST", "OPTIONS"])
@cross_origin(origins=_ALLOWED_ORIGINS, allow_private_network=True)
def collect():
    if request.method == "OPTIONS":
        return "", 204

    if (request.content_length or 0) > MAX_BODY_BYTES:
        return _error(f"Corpo maior que {MAX_BODY_BYTES // 1024} KB.", 413)

    data = _read_body()
    if data is None:
        return _error("Corpo inválido (esperado objeto JSON).", 400)

    key = resolve_key(_extract_key() or str(data.get("key") or "").strip())
    if key is None:
        return _error("Chave de API ausente, inválida ou revogada.", 401)
    if "events:write" not in key.scope_list():
        return _error("Chave sem permissão. Escopo(s) necessário(s): events:write.", 403)
    if rate_limited(key.key_id, limit=COLLECT_RATE_LIMIT, bucket="collect"):
        return _error("Limite de requisições de coleta excedido. Tente de novo em instantes.", 429)
    touch_usage(key)

    visitor_id = data.get("visitor_id")
    if not isinstance(visitor_id, str) or not _ID_RE.match(visitor_id):
        return _error("visitor_id ausente ou inválido (8-64 caracteres: letras, números, _ -).", 400)
    session_id = data.get("session_id")
    if session_id is not None and (not isinstance(session_id, str) or not _ID_RE.match(session_id)):
        return _error("session_id inválido (8-64 caracteres: letras, números, _ -).", 400)

    events = data.get("events")
    if not isinstance(events, list) or not events:
        return _error("Campo 'events' deve ser uma lista não vazia.", 400)
    if len(events) > MAX_BATCH:
        return _error(f"Máximo de {MAX_BATCH} eventos por requisição (recebidos {len(events)}).", 400)

    now = datetime.datetime.now()
    common = {
        "api_key": key.key_id,
        "visitor_id": visitor_id,
        "session_id": session_id,
        "user_ref": _clip(data.get("user_id"), 64),
        "page_url": _clip(data.get("page_url"), 500),
        "page_title": _clip(data.get("page_title"), 200),
        "origin": _clip(request.headers.get("Origin"), 200),
        "received_at": now,
    }

    rows, rejected = [], []
    for index, ev in enumerate(events):
        fields, reason = _validate_item(ev)
        if reason:
            rejected.append({"index": index, "reason": reason})
            continue
        fields["occurred_at"] = _occurred_at(fields["occurred_at"], now)
        rows.append({**common, **fields})

    if not rows:
        return json.dumps({"error": "Nenhum evento válido no lote.", "status": 400,
                           "rejected": rejected}, ensure_ascii=False), 400, \
            {"Content-Type": "application/json; charset=utf-8"}
    try:
        CollectedEvents.insert_many(rows).execute()
    except PeeweeException as err:
        return _error(f"{err}", 500)
    return _ok({"accepted": len(rows), "errors": len(rejected), "rejected": rejected})


@app_collect.route("/collect/events", methods=["GET"])
@require_api_key("tracking:read")
def collected_events():
    """Eventos coletados pelo tracker, do mais antigo ao mais novo.

    Filtros: `since`, `until`, `type`, `visitor_id`, `key_id` (qual material).
    Paginação por cursor: `after_id` + `limit`, igual a /tracking/events.

    O visitor_id sai como está: é um id aleatório gerado no navegador, não
    identifica ninguém por si — ao contrário do student_id, não há o que
    pseudonimizar."""
    try:
        since, err = _date_arg("since")
        if err:
            return _bad_request(err)
        until, err = _date_arg("until")
        if err:
            return _bad_request(err)

        limit = _limit()
        query = CollectedEvents.select()
        after_id = _int_arg("after_id")
        if after_id is not None:
            query = query.where(CollectedEvents.event_id > after_id)
        if since:
            query = query.where(CollectedEvents.occurred_at >= since)
        if until:
            query = query.where(CollectedEvents.occurred_at <= until)
        if request.args.get("type"):
            query = query.where(CollectedEvents.event_type == request.args["type"])
        if request.args.get("visitor_id"):
            query = query.where(CollectedEvents.visitor_id == request.args["visitor_id"])
        key_id = _int_arg("key_id")
        if key_id is not None:
            query = query.where(CollectedEvents.api_key == key_id)

        rows = [{
            "event_id": ev.event_id,
            "key_id": ev.key_id,
            "type": ev.event_type,
            "target": ev.target,
            "visitor_id": ev.visitor_id,
            "session_id": ev.session_id,
            "user_id": ev.user_ref,
            "page_url": ev.page_url,
            "page_title": ev.page_title,
            "context": ev.context,
            "origin": ev.origin,
            "occurred_at": ev.occurred_at,
            "received_at": ev.received_at,
        } for ev in query.order_by(CollectedEvents.event_id.asc()).limit(limit)]
        return _ok(_paged(rows, "event_id", limit))
    except PeeweeException as err:
        return json.dumps({"error": f"{err}", "status": 500}), 500
