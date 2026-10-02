# D.1 — Rota de eventos de aprendizado (xAPI-lite).
#
#   POST /events   body: {events: [{verb, object_type, object_id?, context?,
#                                    occurred_at?}, ...]}  (ou um único objeto)
#
# O aluno vem SEMPRE do token (nunca do payload) — mesma política anti-IDOR das
# demais rotas. Aceita lote (máx. 50/req), valida os verbos contra o enum e é
# best-effort por item: um item inválido não derruba o lote inteiro.
from flask import Blueprint, g
from flask_cors import cross_origin
from peewee import PeeweeException
import json

from edubot.api.auth import require_auth
from edubot.api.http import get_payload
from edubot.services.events import emit_batch, MAX_BATCH

app_event = Blueprint("event", __name__)


@app_event.route("/events", methods=["POST"])
@cross_origin()
@require_auth
def post_events():
    try:
        data = get_payload()
        # Aceita {events:[...]} (contrato) ou um único evento como objeto.
        events = data.get("events") if "events" in data else [data]
        if not isinstance(events, list):
            return json.dumps({"error": "Campo 'events' deve ser uma lista."}), 400
        if len(events) > MAX_BATCH:
            return json.dumps({"error": f"Máximo de {MAX_BATCH} eventos por requisição.",
                               "recebidos": len(events)}), 400

        accepted, errors = emit_batch(g.student, events)
        # Se NADA foi aceito e houve itens, o lote era todo inválido -> 400.
        if accepted == 0 and errors > 0:
            return json.dumps({"error": "Nenhum evento válido no lote.",
                               "erros": errors}), 400
        # G.3 (Plano 2) — qualquer atividade rastreada (login, mídia, leitura)
        # conta para a sequência. Idempotente por dia; best-effort.
        if accepted > 0:
            try:
                from edubot.services.gamification import register_daily_activity
                register_daily_activity(g.student.student_id)
            except Exception:
                pass
        return json.dumps({"accepted": accepted, "errors": errors}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
