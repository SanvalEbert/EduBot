# E.3 (Plano 2) — Metas semanais do aluno logado.
#
#   GET  /goals          -> metas da semana (sugere 2 se ainda não houver;
#                           progresso recalculado dos sinais de XP)
#   POST /goals/accept    -> aceita uma meta sugerida. body: {goal_id}
#
# O aluno vem SEMPRE do token. Metas são parte da gamificação — a rota devolve
# lista vazia quando a gamificação está desligada.
from flask import Blueprint, g
from flask_cors import cross_origin
from peewee import PeeweeException
import json

from edubot.api.auth import require_auth
from edubot.api.http import get_lang, get_payload
from edubot.services import goals as goals_svc
from edubot.services.gamification import gamification_enabled

app_goals = Blueprint("goals", __name__)


@app_goals.route("/goals", methods=["GET"])
@cross_origin()
@require_auth
def get_goals():
    try:
        if not gamification_enabled():
            return json.dumps({"enabled": False, "goals": []}), 200
        sid = g.student.student_id
        state = goals_svc.goals_state(sid, lang=get_lang())
        if not state:
            # sem metas ainda -> sugere na hora (idempotente) e devolve
            goals_svc.suggest_weekly_goals(sid)
            state = goals_svc.goals_state(sid, lang=get_lang())
        return json.dumps({"enabled": True, "goals": state}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_goals.route("/goals/accept", methods=["POST"])
@cross_origin()
@require_auth
def accept_goal():
    try:
        goal_id = get_payload().get("goal_id")
        row = goals_svc.accept_goal(goal_id, g.student.student_id)
        if row is None:
            return json.dumps({"Error": "Meta não encontrada"}), 404
        return json.dumps({"ok": True, "goal_id": row.goal_id, "status": row.status}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
