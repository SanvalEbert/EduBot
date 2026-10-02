# MELHORIA (OVA personalizada) — Rotas da OVA de reforço gerada pelo agente.
#
#   POST /edubot/personalized-ova   -> roda o agente EduBot (tool-use), que
#                                      diagnostica o assunto fraco do aluno
#                                      LOGADO, seleciona conteúdo do banco e
#                                      PERSISTE uma OVA personalizada.
#   GET  /personalized-ova          -> lista as OVAs personalizadas do aluno.
#   GET  /personalized-ova/<id>     -> conteúdo da OVA (recursos + questões),
#                                      no MESMO formato de /ova/<id>/resources e
#                                      /question/ova, para o frontend reaproveitar
#                                      os players e o quiz existentes.
#
# Todas exigem token (@require_auth). O aluno vem de g.student (nunca do
# payload), e o acesso a uma OVA personalizada é restrito ao seu dono.


from flask import Blueprint, g, request
from flask_cors import cross_origin
from peewee import PeeweeException
import json
import datetime

from edubot.data.models.competencies import Competencies
from edubot.data.models.questions import Questions
from edubot.data.models.answers import Answers
from edubot.data.models.resources import Resources
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.interventions import Interventions
from edubot.data.models.personalized_ova import PersonalizedOVA, PersonalizedOVAItem

from edubot.api.auth import require_auth
from edubot.api.http import get_lang
from edubot.i18n import tr
from edubot.services.student_context import build_student_profile
# A.6: _alternatives_list agora vem da fonte única (era duplicada com questionRoute).
from edubot.services.quiz import alternatives_list as _alternatives_list
from edubot.agent import run_personalized_ova_agent

app_personalized_ova = Blueprint("personalized_ova", __name__)


@app_personalized_ova.route("/edubot/personalized-ova", methods=["POST"])
@cross_origin()
@require_auth
def create_personalized_ova():
    try:
        # 1. Perfil completo do aluno logado (mesma entrada do EduBot 4.3)
        profile = build_student_profile(g.student)

        # Fase 4 — alvo explícito (opcional): o CTA de uma intervenção de reforço
        # manda a competência que o aluno acabou de errar, para a trilha ser
        # sobre o que ele estudou agora e não sobre a pior competência global.
        # Só aceitamos competência do PRÓPRIO perfil do aluno (escopo do curso).
        #
        # Lido direto (não por get_payload) porque aqui o CORPO É OPCIONAL: a
        # chamada histórica não manda nada, e get_payload aborta com 400 nesse caso.
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = {}
        target_competency_id = payload.get("competency_id")
        if target_competency_id is not None:
            try:
                target_competency_id = int(target_competency_id)
            except (TypeError, ValueError):
                return json.dumps({"Error": "competency_id inválido"}), 400
            do_curso = {c["competency_id"] for c in profile.get("competencias", [])}
            if target_competency_id not in do_curso:
                return json.dumps({"Error": "Competência fora do curso do aluno"}), 400

        # 2. Agente de tool-use: diagnostica, busca conteúdo e monta a OVA
        result = run_personalized_ova_agent(g.student, profile, target_competency_id)

        if not result.get("personalized_ova_id"):
            return json.dumps({
                "Error": "Não foi possível montar a OVA personalizada "
                         "(sem conteúdo de reforço para a competência fraca).",
                "detalhe": result.get("mensagem_final")
            }, default=str), 422

        pova = PersonalizedOVA.get_by_id(result["personalized_ova_id"])

        # 3. Registra no histórico de intervenções (consumido pelo painel)
        Interventions.create(
            student_id=g.student,
            date=datetime.date.today(),
            type="ova_personalizada",
            description=pova.message,
            result="pendente")

        return json.dumps({
            "personalized_ova_id": pova.personalized_ova_id,
            "titulo": pova.title,
            "mensagem_aluno": pova.message,
            "justificativa": pova.rationale,
            "target_competency_id": (pova.target_competency_id.competency_id
                                     if pova.target_competency_id else None),
            "itens_recursos": result["resultado"].get("itens_recursos", 0),
            "itens_questoes": result["resultado"].get("itens_questoes", 0),
            "mock": result.get("mock"),
            "model_id": result.get("model_id"),
            # P.2 — formato preferido pelo qual a trilha começou (chip no front).
            "formato_preferido": result.get("formato_preferido"),
        }, default=str), 201
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_personalized_ova.route("/personalized-ova", methods=["GET"])
@cross_origin()
@require_auth
def list_personalized_ovas():
    try:
        lang = get_lang()
        ovas = []
        for pova in (PersonalizedOVA
                     .select()
                     .where(PersonalizedOVA.student_id == g.student)
                     .order_by(PersonalizedOVA.created_at.desc())):
            comp = pova.target_competency_id
            ovas.append({
                "personalized_ova_id": pova.personalized_ova_id,
                "titulo": pova.title,
                "status": pova.status,
                "created_at": str(pova.created_at),
                "competencia": tr(comp.competency_description,
                                  comp.competency_description_en, lang) if comp else None,
            })
        return json.dumps(ovas, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_personalized_ova.route("/personalized-ova/<int:pova_id>", methods=["GET"])
@cross_origin()
@require_auth
def get_personalized_ova(pova_id):
    try:
        pova = PersonalizedOVA.get_or_none(
            (PersonalizedOVA.personalized_ova_id == pova_id) &
            (PersonalizedOVA.student_id == g.student))
        if pova is None:
            # 404 também quando é de outro aluno (não vaza existência)
            return json.dumps({"Error": "OVA personalizada não encontrada"}), 404

        lang = get_lang()
        items = (PersonalizedOVAItem
                 .select()
                 .where(PersonalizedOVAItem.personalized_ova_id == pova)
                 .order_by(PersonalizedOVAItem.position))

        recursos = []
        questoes = []
        for item in items:
            if item.item_kind == "resource" and item.resource_id is not None:
                resource = Resources.get_or_none(Resources.resource_id == item.resource_id)
                if resource is None:
                    continue
                rp = ResourceProgress.get_or_none(
                    (ResourceProgress.student_id == g.student) &
                    (ResourceProgress.resource_id == resource.resource_id))
                recursos.append({
                    "resource_id": resource.resource_id,
                    "resource_type": resource.resource_type,
                    "resource_title": tr(resource.resource_title, resource.resource_title_en, lang),
                    "resource_url": resource.resource_url,
                    "media_type": resource.media_type,
                    "duration_seconds": resource.duration_seconds,
                    "perc_consumed": rp.perc_consumed if rp else 0,
                    "seconds_consumed": rp.seconds_consumed if rp else 0,
                    "completed": bool(rp.completed) if rp else False,
                })
            elif item.item_kind == "question" and item.question_id is not None:
                question = Questions.get_or_none(Questions.question_id == item.question_id)
                if question is None:
                    continue
                answered = (Answers
                            .select()
                            .where((Answers.student_id == g.student) &
                                   (Answers.question_id == question.question_id))
                            .exists())
                questoes.append({
                    "question_id": question.question_id,
                    "statement": tr(question.statement, question.statement_en, lang),
                    "alternatives": _alternatives_list(question, lang),
                    "answered": answered,
                    "competency_id": question.competency_id.competency_id,
                })

        # P.2 — o chip "no seu formato" ao reabrir: reflete o formato pelo qual a
        # trilha foi ORDENADA (o 1º recurso). Só mostra se a trilha realmente
        # começa por um formato de mídia consumível (vídeo/texto/podcast).
        formato_preferido = recursos[0]["resource_type"] if recursos and \
            recursos[0]["resource_type"] in ("video", "texto", "podcast") else None

        comp = pova.target_competency_id
        return json.dumps({
            "personalized_ova_id": pova.personalized_ova_id,
            "titulo": pova.title,
            "mensagem_aluno": pova.message,
            "justificativa": pova.rationale,
            "status": pova.status,
            "created_at": str(pova.created_at),
            "competencia": {
                "competency_id": comp.competency_id,
                "nome": tr(comp.competency_description,
                           comp.competency_description_en, lang),
            } if comp else None,
            "formato_preferido": formato_preferido,
            "recursos": recursos,
            "questoes": questoes,
        }, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
