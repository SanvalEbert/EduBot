# G.4/G.5 (Plano 2) — Gamificação: cabeçalho de jornada, ranking e opt-in.
#
#   GET  /gamification/me           -> nível + barra de XP, sequência, XP da
#                                      semana, vitrine de conquistas, título.
#   GET  /gamification/leaderboard  -> ranking semanal da turma (só quem fez
#                                      opt-in é listado; o aluno sempre vê a
#                                      própria posição/percentil).
#   POST /gamification/participate  -> entra no ranking: grava apelido +
#                                      consentimento `ranking_turma`. body:{nickname}
#
# O aluno vem SEMPRE do token. Ranking é opt-in (LGPD): expor apelido/XP aos
# colegas é finalidade nova de consentimento; revogar (em "Meus dados") esconde.
from flask import Blueprint, g
from flask_cors import cross_origin
from peewee import PeeweeException
import json

from edubot.api.auth import require_auth
from edubot.api.http import get_lang, get_payload
from edubot.services import gamification as G
from edubot.services.consents import set_consent

app_gamification = Blueprint("gamification", __name__)


@app_gamification.route("/gamification/me", methods=["GET"])
@cross_origin()
@require_auth
def gamification_me():
    try:
        return json.dumps(G.me_state(g.student, get_lang()), default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_gamification.route("/gamification/leaderboard", methods=["GET"])
@cross_origin()
@require_auth
def gamification_leaderboard():
    try:
        if not G.gamification_enabled():
            return json.dumps({"enabled": False, "top": [], "me": None}), 200
        data = G.leaderboard(g.student)
        data["enabled"] = True
        return json.dumps(data, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_gamification.route("/gamification/title", methods=["POST"])
@cross_origin()
@require_auth
def gamification_title():
    """R.2 — escolhe o título ativo (entre os concedidos por conquistas). body:
    {title_id} — vazio limpa o título."""
    try:
        title_id = get_payload().get("title_id")
        label = G.set_title(g.student, title_id)
        if title_id and label is None:
            return json.dumps({"error": "Título não conquistado."}), 400
        return json.dumps({"ok": True, "title": label}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_gamification.route("/gamification/participate", methods=["POST"])
@cross_origin()
@require_auth
def gamification_participate():
    """Entra no ranking (opt-in): grava apelido + consentimento. Também usado para
    trocar o apelido. Apelido é obrigatório para participar."""
    try:
        nickname = (get_payload().get("nickname") or "").strip()[:40]
        if len(nickname) < 2:
            return json.dumps({"error": "Escolha um apelido (mín. 2 caracteres)."}), 400
        student = g.student
        # AUDITORIA P2: apelido é a identidade pública no ranking — não pode
        # colidir com o de OUTRO aluno do mesmo curso (evita personificação e
        # ambiguidade no placar). Case-insensitive.
        from edubot.data.models.students import Students
        from peewee import fn as _fn
        taken = (Students
                 .select()
                 .where((Students.course_id == student.course_id) &
                        (Students.student_id != student.student_id) &
                        (_fn.LOWER(Students.nickname) == nickname.lower()))
                 .exists())
        if taken:
            return json.dumps({"error": "Este apelido já está em uso na sua turma."}), 409
        student.nickname = nickname
        student.save()
        set_consent(student, "ranking_turma", True)
        return json.dumps({"ok": True, "nickname": nickname,
                           "participando": True}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
