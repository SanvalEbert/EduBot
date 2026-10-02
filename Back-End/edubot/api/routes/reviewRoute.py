# D.3 — Agenda de revisão espaçada do aluno logado.
#
#   GET /reviews   -> revisões vencidas + as que vencem nos próximos 7 dias
#
# Alimenta a seção "Revisões desta semana" em "Meu desempenho". O aluno vem do
# token; as competências vêm traduzidas conforme ?lang= (A12).
from flask import Blueprint, g
from flask_cors import cross_origin
from peewee import PeeweeException, fn
import datetime
import json

from edubot.api.auth import require_auth
from edubot.api.http import get_lang
from edubot.i18n import tr
from edubot.data.models.competencies import Competencies
from edubot.data.models.questions import Questions
from edubot.services.reviews import due_reviews

app_review = Blueprint("review", __name__)


@app_review.route("/reviews", methods=["GET"])
@cross_origin()
@require_auth
def get_reviews():
    try:
        lang = get_lang()
        today = datetime.date.today()
        rows = due_reviews(g.student.student_id, today=today)
        # nomes das competências (1 query)
        comp_ids = [r.competency_id.competency_id for r in rows]
        nomes = {c.competency_id: tr(c.competency_description,
                                     c.competency_description_en, lang)
                 for c in Competencies.select().where(Competencies.competency_id.in_(comp_ids))}
        # OVA para revisar cada competência: o menor ova_id que tem questões dela.
        # Alimenta o botão "Revisar" (abre o quiz certo). None se a competência não
        # tem questões cadastradas (o botão simplesmente não aparece).
        ova_por_comp = {q["competency"]: q["ova"] for q in (Questions
                        .select(Questions.competency_id.alias("competency"),
                                fn.MIN(Questions.ova_id).alias("ova"))
                        .where(Questions.competency_id.in_(comp_ids))
                        .group_by(Questions.competency_id)
                        .dicts())}
        out = [{
            "review_id": r.review_id,
            "competency_id": r.competency_id.competency_id,
            "competencia": nomes.get(r.competency_id.competency_id),
            "ova_id": ova_por_comp.get(r.competency_id.competency_id),
            "due_date": str(r.due_date),
            "status": "vencida" if r.due_date <= today else r.status,
            "vencida": r.due_date <= today,
            "interval_days": r.interval_days,
        } for r in rows]
        return json.dumps({"reviews": out}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
