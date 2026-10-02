# MELHORIA (4.3) — Rota do agente EduBot.
#
#   GET /edubot/recommendation -> gera a recomendação para o aluno LOGADO
#                                 (perfil completo -> edubot_agent -> JSON)
#
# Cada recomendação gerada é persistida na tabela "interventions", que passa a
# funcionar como histórico de intervenções do EduBot (consumido pelo painel e
# devolvido dentro do próprio perfil em historico_intervencoes).



from flask import Blueprint, request, g
from flask_cors import cross_origin
from edubot.api.http import get_payload
from peewee import PeeweeException
import json
import datetime

from edubot.data.models.interventions import Interventions
from edubot.data.models.ovas import OVAs
from edubot.data.models.competencies import Competencies

from edubot.api.auth import require_auth
from edubot.api.http import get_lang
from edubot.i18n import tr
from edubot.services.student_context import build_student_profile
from edubot.services.decisions import record_decision
from edubot.services.events import emit as emit_event
from edubot.services.consents import has_consent
from edubot.agent import get_recommendation
from edubot.agent.tutor import tutor_reply
from edubot.agent.external_sources import search_external
from edubot.agent.coach import coach_message

app_edubot = Blueprint("edubot", __name__)


@app_edubot.route("/edubot/recommendation", methods=["GET"])
@cross_origin()
@require_auth
def edubot_recommendation():
    try:
        lang = get_lang()
        # 1. Monta o perfil completo do aluno logado (contexto 4.2)
        profile = build_student_profile(g.student, lang=lang)

        # 2. Chama o agente no idioma do aluno (Fase 4 — A12). D.5: sem
        #    consentimento de IA sobre dados, roda só as regras (allow_llm=False).
        allow_llm = has_consent(g.student, "ia_sobre_dados")
        recommendation = get_recommendation(profile, lang=lang, allow_llm=allow_llm)

        # 3. Persiste como intervenção para compor o histórico — deduplicado (A8).
        #    O endpoint é um GET consultado a cada clique do aluno; sem dedup,
        #    cinco cliques criavam cinco intervenções "pendente" iguais poluindo
        #    o histórico e o próprio perfil que o agente lê. Só cria se ainda não
        #    houver uma intervenção pendente do mesmo tipo no dia.
        today = datetime.date.today()
        already = (
            Interventions
            .select()
            .where(
                (Interventions.student_id == g.student) &
                (Interventions.date == today) &
                (Interventions.type == recommendation["tipo"]) &
                (Interventions.result == "pendente")
            )
            .exists()
        )
        if not already:
            Interventions.create(
                student_id=g.student,
                date=today,
                type=recommendation["tipo"],
                description=recommendation["mensagem_aluno"],
                result="pendente"
            )

        # B.2 — registra a decisão sob demanda (digest minimizado, sem RA/nome).
        record_decision(
            g.student, "on_demand",
            input_digest={
                "dias_sem_acesso": profile["dias_sem_acesso"],
                "percentual_consumido": profile["recursos"]["percentual_consumido"],
                "taxa_erro_quiz": profile["quiz"]["taxa_erro"],
                "tipo": recommendation.get("tipo"),
                "prioridade": recommendation.get("prioridade"),
                # P.1/P.3 — formato proposto (sensor de preferência via B.6).
                "formato_sugerido": recommendation.get("formato_preferido"),
            },
            model_id=recommendation.get("model_id"),
            mock=recommendation.get("mock", True),
            actions=[{"type": "intervention", "tipo": recommendation.get("tipo")}])

        return json.dumps({
            "recommendation": recommendation,
            "profile_summary": {
                "dias_sem_acesso": profile["dias_sem_acesso"],
                "percentual_consumido": profile["recursos"]["percentual_consumido"],
                "taxa_erro_quiz": profile["quiz"]["taxa_erro"],
                "atividades_pendentes": profile["atividades_pendentes"],
                "preferencia_formato": profile["preferencia_formato"]
            }
        }, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# MELHORIA (Tutor IA por OVA) — chat de tutoria restrito ao conteúdo do OVA.
#
#   POST /edubot/tutor-chat  body: [{ova_id, context, messages}]
#
# O tutor responde com base SOMENTE no material do OVA (grounding). O título é
# resolvido do banco (validando o ova_id); o material (context) é o texto do
# conteúdo que o aluno consumiu, enviado pelo frontend. O "cérebro" está mockado
# (ver edubot_agent/tutor.py) — o contrato já é o da LLM real.
@app_edubot.route("/edubot/tutor-chat", methods=["POST"])
@cross_origin()
@require_auth
def edubot_tutor_chat():
    try:
        data = get_payload()
    except (TypeError, IndexError, KeyError):
        return json.dumps({"Error": "Invalid payload"}), 400

    ova_id = data.get("ova_id")
    ova = OVAs.get_or_none(OVAs.ova_id == ova_id) if ova_id is not None else None
    if ova is None:
        return json.dumps({"Error": "Unknown ova_id"}), 400

    # Aceita apenas papéis válidos e mensagens não vazias (sanitização básica).
    messages = []
    for m in (data.get("messages") or []):
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    if not messages or messages[-1]["role"] != "user":
        return json.dumps({"Error": "A última mensagem deve ser do aluno (user)."}), 400

    lang = get_lang()
    result = tutor_reply(
        titulo=tr(ova.ova_name, ova.ova_name_en, lang),
        context=data.get("context") or "",
        messages=messages,
        lang=lang,
        persona=data.get("persona"),   # CP.4: estilo do personagem (tom, não regras)
    )

    # D.1 — `asked_tutor` é o sinal diagnóstico mais rico (é o que torna a
    # intervenção do redator específica, B.4). Emitido AQUI no backend: o texto
    # da pergunta só é persistido com consentimento `ia_sobre_dados` — a
    # minimização acontece dentro de events.emit (D.5), não na UI.
    emit_event(g.student, "asked_tutor", "ova", ova_id,
               text=messages[-1]["content"])

    # G.1 (Plano 2) — perguntar ao tutor é esforço (teto 2/dia): concede XP e
    # conta como dia de estudo. Best-effort, flag-guarded.
    try:
        from edubot.services.gamification import award, register_daily_activity
        register_daily_activity(g.student.student_id)
        award(g.student.student_id, "pergunta_ao_tutor", "ova", ova_id)
    except Exception:
        pass

    # B.2 — chamada REAL ao LLM conta no orçamento diário; só metadados/tokens
    # (o conteúdo do chat vai para os eventos acima, não para a trilha).
    if not result.get("mock", True):
        record_decision(
            g.student, "chat",
            input_digest={"ova_id": ova_id},
            model_id=result.get("model_id"), mock=False,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0))

    return json.dumps({
        "reply": result["reply"],
        "ova_id": ova_id,
        "ova_name": tr(ova.ova_name, ova.ova_name_en, lang),
        "model_id": result["model_id"],
        "mock": result["mock"],
        "sources": result.get("sources", []),
    }, default=str), 200


# MELHORIA (Roteiro Cena 4) — materiais externos (bases científicas) por
# competência. Cruza a lacuna de competência com artigos de fora da plataforma.
@app_edubot.route("/edubot/external-resources", methods=["GET"])
@cross_origin()
@require_auth
def edubot_external_resources():
    competency_id = request.args.get("competency_id", type=int)
    comp = Competencies.get_or_none(Competencies.competency_id == competency_id) if competency_id else None
    if comp is None:
        return json.dumps({"Error": "Unknown competency_id"}), 400

    resultados = search_external(comp.competency_description, limit=3)
    return json.dumps({
        "competency_id": competency_id,
        "competencia": comp.competency_description,
        "resultados": resultados,
    }, default=str), 200


# MELHORIA (Roteiro Cena 3) — fala do EduBot (coach) sobre o progresso do aluno,
# gerada por IA (Bedrock) sob demanda. Se a IA não estiver disponível, devolve
# message=null e o frontend usa o texto local (determinístico).
@app_edubot.route("/edubot/coach-message", methods=["GET"])
@cross_origin()
@require_auth
def edubot_coach_message():
    lang = request.args.get("lang", "pt")
    persona = request.args.get("persona")   # CP.4: estilo do personagem (opcional)
    try:
        profile = build_student_profile(g.student)
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500

    result = coach_message(profile, lang=lang, persona=persona)
    if not result:
        return json.dumps({"message": None, "ai": False}), 200
    text, model_id = result
    return json.dumps({"message": text, "ai": True, "model_id": model_id}, default=str), 200


# MELHORIA (A13 — proatividade) — intervenções NÃO LIDAS do aluno logado.
#
#   GET  /edubot/interventions        -> intervenções pendentes (o EduBot "falou
#                                        primeiro"), para o dashboard exibir
#   POST /edubot/intervention/ack     -> marca uma intervenção como lida
#
# São as intervenções criadas pelos gatilhos por evento e pela varredura
# agendada; o aluno as vê no dashboard sem precisar pedir uma recomendação.
@app_edubot.route("/edubot/interventions", methods=["GET"])
@cross_origin()
@require_auth
def edubot_interventions():
    try:
        rows = (Interventions
                .select()
                .where((Interventions.student_id == g.student) &
                       (Interventions.result == "pendente"))
                .order_by(Interventions.date.desc())
                .limit(10))
        out = [{
            "intervention_id": it.intervention_id,
            "data": str(it.date),
            "tipo": it.type,
            "descricao": it.description,
            "resultado": it.result,
        } for it in rows]
        return json.dumps({"interventions": out}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_edubot.route("/edubot/intervention/ack", methods=["POST"])
@cross_origin()
@require_auth
def edubot_intervention_ack():
    data = get_payload()
    intervention_id = data.get("intervention_id")
    try:
        # Só o dono pode marcar como lida (aluno vem do token).
        it = Interventions.get_or_none(
            (Interventions.intervention_id == intervention_id) &
            (Interventions.student_id == g.student))
        if it is None:
            return json.dumps({"Error": "Intervenção não encontrada"}), 404
        it.result = "lida"
        it.save()
        # D.1 — evento discreto: o aluno reconheceu/dispensou a intervenção. É o
        # par do `received_intervention` (permite medir aceite/dispensa em B.6).
        emit_event(g.student, "dismissed", "intervention", it.intervention_id,
                   tipo=it.type, result="lida")
        return json.dumps({"ok": True, "intervention_id": intervention_id}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
