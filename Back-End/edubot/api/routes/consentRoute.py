# D.5 — Consentimento (LGPD) e direitos do titular.
#
#   GET  /consents                    -> estado das 3 finalidades do aluno logado
#   POST /consents                    -> grava/atualiza um consentimento
#                                        body: {purpose, granted}
#   POST /student/me/delete-request   -> registra pedido de exclusão (vira alerta
#                                        para o admin; exclusão efetiva é manual)
#
# O aluno vem SEMPRE do token. `tracking_pedagogico` é informado/execução de
# contrato: aceito, mas não revogável (o serviço É o rastreamento).
from flask import Blueprint, g
from flask_cors import cross_origin
from peewee import PeeweeException
import json
import datetime

from edubot.api.auth import require_auth
from edubot.api.http import get_payload
from edubot.services.consents import current_consents, set_consent, PURPOSES
from edubot.data.models.alerts import Alerts

app_consent = Blueprint("consent", __name__)


@app_consent.route("/consents", methods=["GET"])
@cross_origin()
@require_auth
def get_consents():
    try:
        return json.dumps({"consents": current_consents(g.student)}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_consent.route("/consents", methods=["POST"])
@cross_origin()
@require_auth
def post_consent():
    try:
        data = get_payload()
        purpose = data.get("purpose")
        if purpose not in PURPOSES:
            return json.dumps({"error": "Finalidade inválida.",
                               "aceitas": list(PURPOSES)}), 400
        granted = bool(data.get("granted"))
        set_consent(g.student, purpose, granted)
        # Devolve o estado completo — o front atualiza a tela "Meus dados" de uma vez.
        return json.dumps({"consents": current_consents(g.student)}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_consent.route("/student/me/delete-request", methods=["POST"])
@cross_origin()
@require_auth
def request_deletion():
    """Direito de exclusão (LGPD): na v1 a exclusão efetiva é manual (o admin
    executa o DELETE, e os ON DELETE CASCADE do schema propagam). O pedido vira
    um alerta de severidade alta para o admin. Idempotente: um pedido pendente
    por aluno."""
    try:
        student = g.student
        already = (Alerts
                   .select()
                   .where((Alerts.student_id == student) &
                          (Alerts.type == "delete_request") &
                          (Alerts.read == False))
                   .exists())
        if not already:
            Alerts.create(
                student_id=student, type="delete_request",
                message=f"{student.student_name} solicitou a exclusão dos seus dados (LGPD).",
                severity="alta", created_at=datetime.datetime.now(), read=False)
        return json.dumps({"ok": True, "status": "pendente"}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
