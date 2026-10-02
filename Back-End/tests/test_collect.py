"""Coleta de eventos do edubot-tracker.js (POST /api/v1/collect).

O que estes testes travam:
  1. Só grava com chave válida E escopo `events:write` (401/403).
  2. A chave pode vir no corpo, e o corpo pode ser text/plain — é o formato do
     navigator.sendBeacon, usado quando a página fecha. Se isso quebrar, os
     eventos de saída (tempo na página) somem sem erro visível no navegador.
  3. CORS aberto na coleta, inclusive preflight — o script roda em outro site.
  4. Lote best-effort: item ruim é rejeitado com motivo, o resto grava.
  5. Chave de coleta (pública, vai no HTML) não lê nada.
"""
import datetime
import json

import pytest

from edubot.data.models.api_keys import ApiKeys
from edubot.data.models.collected_events import CollectedEvents

URL = "/api/v1/collect"
VISITOR = "v1a2b3c4d5e6f7a8"


def _body(key=None, events=None, **extra):
    body = {"visitor_id": VISITOR, "session_id": "s1a2b3c4d5",
            "page_url": "file:///C:/teste/material.html", "page_title": "Material de teste",
            "events": events if events is not None else [
                {"type": "click", "target": "botao-teste", "context": {"tag": "button"}}]}
    if key:
        body["key"] = key
    body.update(extra)
    return body


def _post(client, body, headers=None, content_type="application/json"):
    return client.post(URL, data=json.dumps(body), headers=headers or {},
                       content_type=content_type)


def _write_key(api_key):
    return api_key("events:write")["X-API-Key"]


# ---------------------------------------------------------------------------
# Autenticação e escopo
# ---------------------------------------------------------------------------
def test_sem_chave_e_401(client):
    assert _post(client, _body()).status_code == 401
    assert CollectedEvents.select().count() == 0


def test_chave_invalida_e_401(client):
    assert _post(client, _body(key="ek_live_naoexiste")).status_code == 401


def test_chave_sem_events_write_e_403(client, api_key):
    raw = api_key("tracking:read")["X-API-Key"]
    resp = _post(client, _body(key=raw))
    assert resp.status_code == 403
    assert "events:write" in json.loads(resp.data)["error"]


def test_chave_revogada_e_401(client, api_key):
    raw = api_key("events:write", active=False)["X-API-Key"]
    assert _post(client, _body(key=raw)).status_code == 401


def test_chave_no_header_funciona(client, api_key):
    headers = {"X-API-Key": _write_key(api_key)}
    assert _post(client, _body(), headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------
def test_grava_evento_com_todos_os_campos(client, api_key):
    raw = _write_key(api_key)
    resp = _post(client, _body(key=raw, user_id="lucas-01"),
                 headers={"Origin": "https://material.exemplo.com"})
    assert resp.status_code == 200
    assert json.loads(resp.data) == {"accepted": 1, "errors": 0, "rejected": []}

    ev = CollectedEvents.get()
    key = ApiKeys.get(ApiKeys.key_prefix == raw[:16])
    assert ev.key_id == key.key_id
    assert ev.event_type == "click"
    assert ev.target == "botao-teste"
    assert ev.visitor_id == VISITOR
    assert ev.session_id == "s1a2b3c4d5"
    assert ev.user_ref == "lucas-01"
    assert ev.page_title == "Material de teste"
    assert ev.context == {"tag": "button"}
    assert ev.origin == "https://material.exemplo.com"


def test_sendbeacon_text_plain_com_chave_no_corpo(client, api_key):
    """O formato exato que o tracker usa ao fechar a página."""
    resp = _post(client, _body(key=_write_key(api_key)), content_type="text/plain")
    assert resp.status_code == 200
    assert CollectedEvents.select().count() == 1


def test_uso_da_chave_e_contabilizado(client, api_key):
    raw = _write_key(api_key)
    _post(client, _body(key=raw))
    _post(client, _body(key=raw))
    assert ApiKeys.get(ApiKeys.key_prefix == raw[:16]).request_count == 2


def test_lote_misto_grava_validos_e_explica_rejeitados(client, api_key):
    events = [
        {"type": "click", "target": "ok-1"},
        {"type": "tipo com espaço"},
        {"target": "sem-type"},
        {"type": "page_view"},
        {"type": "click", "context": "nao-e-objeto"},
    ]
    resp = _post(client, _body(key=_write_key(api_key), events=events))
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data["accepted"] == 2 and data["errors"] == 3
    assert [r["index"] for r in data["rejected"]] == [1, 2, 4]
    assert CollectedEvents.select().count() == 2


def test_lote_todo_invalido_e_400(client, api_key):
    resp = _post(client, _body(key=_write_key(api_key), events=[{"type": ""}]))
    assert resp.status_code == 400
    assert CollectedEvents.select().count() == 0


def test_context_grande_demais_e_rejeitado(client, api_key):
    events = [{"type": "click", "context": {"x": "a" * 3000}}]
    assert _post(client, _body(key=_write_key(api_key), events=events)).status_code == 400


@pytest.mark.parametrize("visitor", [None, "curto", "tem espaço aqui", "x" * 65])
def test_visitor_id_invalido_e_400(client, api_key, visitor):
    body = _body(key=_write_key(api_key))
    body["visitor_id"] = visitor
    assert _post(client, body).status_code == 400


def test_lote_acima_do_maximo_e_400(client, api_key):
    events = [{"type": "click"}] * 51
    assert _post(client, _body(key=_write_key(api_key), events=events)).status_code == 400


def test_corpo_que_nao_e_json_e_400(client):
    resp = client.post(URL, data="isso nao e json", content_type="text/plain")
    assert resp.status_code == 400


def test_horario_do_cliente_absurdo_vira_horario_de_chegada(client, api_key):
    futuro = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)).isoformat()
    events = [{"type": "click", "occurred_at": futuro}]
    antes = datetime.datetime.now()
    _post(client, _body(key=_write_key(api_key), events=events))
    ev = CollectedEvents.get()
    assert antes - datetime.timedelta(seconds=5) <= ev.occurred_at <= datetime.datetime.now()


def test_horario_do_cliente_valido_e_preservado(client, api_key):
    """O tracker manda UTC (toISOString); gravamos em hora local, como o resto."""
    dez_min_atras = datetime.datetime.now() - datetime.timedelta(minutes=10)
    utc = dez_min_atras.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _post(client, _body(key=_write_key(api_key), events=[{"type": "click", "occurred_at": utc}]))
    ev = CollectedEvents.get()
    assert abs((ev.occurred_at - dez_min_atras).total_seconds()) < 1


def test_textos_longos_sao_truncados(client, api_key):
    body = _body(key=_write_key(api_key), page_title="T" * 500,
                 events=[{"type": "click", "target": "b" * 500}])
    assert _post(client, body).status_code == 200
    ev = CollectedEvents.get()
    assert len(ev.page_title) == 200 and len(ev.target) == 120


# ---------------------------------------------------------------------------
# CORS — o script roda em outro site (ou em file://, Origin: null)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("origin", ["https://material.exemplo.com", "null"])
def test_cors_liberado_na_coleta(client, api_key, origin):
    resp = _post(client, _body(key=_write_key(api_key)), headers={"Origin": origin})
    assert resp.headers.get("Access-Control-Allow-Origin") in ("*", origin)


def test_preflight_da_coleta(client):
    resp = client.options(URL, headers={
        "Origin": "https://material.exemplo.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-api-key",
    })
    assert resp.status_code in (200, 204)
    assert resp.headers.get("Access-Control-Allow-Origin") in ("*", "https://material.exemplo.com")


# ---------------------------------------------------------------------------
# Leitura do que foi coletado
# ---------------------------------------------------------------------------
def test_chave_de_coleta_nao_le_nada(client, api_key):
    headers = api_key("events:write")
    for url in ("/api/v1/collect/events", "/api/v1/tracking/events", "/api/v1/students"):
        assert client.get(url, headers=headers).status_code == 403


def test_leitura_dos_eventos_coletados_com_cursor(client, api_key):
    raw = _write_key(api_key)
    events = [{"type": "click", "target": f"b{i}"} for i in range(5)]
    _post(client, _body(key=raw, events=events))

    headers = api_key("tracking:read")
    vistos, after = [], None
    while True:
        url = "/api/v1/collect/events?limit=2" + (f"&after_id={after}" if after else "")
        page = json.loads(client.get(url, headers=headers).data)
        vistos += [r["target"] for r in page["data"]]
        after = page["next_after_id"]
        if after is None:
            break
    assert vistos == ["b0", "b1", "b2", "b3", "b4"]


def test_leitura_filtra_por_tipo_e_visitante(client, api_key):
    raw = _write_key(api_key)
    _post(client, _body(key=raw, events=[{"type": "click"}, {"type": "page_view"}]))
    outro = _body(key=raw, events=[{"type": "click"}])
    outro["visitor_id"] = "outro-visitante-99"
    _post(client, outro)

    headers = api_key("tracking:read")
    cliques = json.loads(client.get("/api/v1/collect/events?type=click", headers=headers).data)
    assert cliques["count"] == 2
    do_visitante = json.loads(client.get(
        f"/api/v1/collect/events?visitor_id={VISITOR}", headers=headers).data)
    assert do_visitante["count"] == 2


# ---------------------------------------------------------------------------
# apikey_tool — chave pública não pode ler
# ---------------------------------------------------------------------------
def test_tool_recusa_events_write_com_leitura():
    from tools.apikey_tool import _parse_scopes
    with pytest.raises(SystemExit):
        _parse_scopes("events:write,tracking:read")
    assert _parse_scopes("events:write") == ["events:write"]
