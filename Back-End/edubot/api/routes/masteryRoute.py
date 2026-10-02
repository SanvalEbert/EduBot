# H.1 (Plano 2) — tendência de domínio do aluno logado (últimos 7 dias).
#
#   GET /mastery/trend  -> por competência: domínio atual, anterior, delta e
#                          direção (up|down|flat). Alimenta as SETAS de tendência
#                          na teia de competências (Etapa 8/G.5).
#
# Rota barata e SEPARADA do /student/me de propósito: o perfil é o caminho quente
# (<= 8 queries, teste de contrato); a tendência só é pedida na tela de desempenho.
from flask import Blueprint, g
from flask_cors import cross_origin
from peewee import PeeweeException
import json

from edubot.api.auth import require_auth
from edubot.api.http import get_lang
from edubot.i18n import tr
from edubot.data.models.competencies import Competencies
from edubot.services.mastery import mastery_trend

app_mastery = Blueprint("mastery", __name__)


@app_mastery.route("/mastery/trend", methods=["GET"])
@cross_origin()
@require_auth
def get_mastery_trend():
    try:
        lang = get_lang()
        trend = mastery_trend(g.student.student_id)
        if not trend:
            return json.dumps({"trend": []}), 200
        nomes = {c.competency_id: tr(c.competency_description,
                                     c.competency_description_en, lang)
                 for c in Competencies.select().where(
                     Competencies.competency_id.in_(list(trend.keys())))}
        out = [{
            "competency_id": cid,
            "competencia": nomes.get(cid),
            **vals,
        } for cid, vals in trend.items()]
        # mais movimento primeiro (maior |delta|)
        out.sort(key=lambda x: -abs(x["delta"]))
        return json.dumps({"trend": out}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
