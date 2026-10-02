# Import necessary libraries
from flask import Blueprint, request, g
from flask_cors import cross_origin
from edubot.api.http import get_payload
from peewee import PeeweeException # ORM library
import json

# Import the necessary ORM classes
from edubot.data.models.questions import Questions
from edubot.data.models.answers import Answers
from edubot.data.models.attempts import Attempts
from edubot.data.models.ovas import OVAs

from edubot.api.auth import require_auth
from edubot.api.http import get_lang
from edubot.i18n import tr
from edubot.services.proactivity import trigger_evaluation
# A.6: _alternatives_list era duplicada aqui e em personalizedOvaRoute; agora vem
# da fonte única edubot.services.quiz. U.1: gate de liberação do quiz.
from edubot.services.quiz import (alternatives_list as _alternatives_list, quiz_unlocked,
                                  adaptive_pool, difficulty_overrides_for, challenge_pool)
# D.1: evento de aprendizado (answered). D.2: mastery por competência (BKT).
from edubot.services.events import emit as emit_event
from edubot.services.mastery import update_on_attempt, mastery_map
from edubot.services.reviews import on_attempt as review_on_attempt
from edubot.services.reinforcement import suggest_reinforcement

# Create a route blueprint as a reusable component
app_question = Blueprint("question", __name__)


def _gamify_answer(student, question, ova):
    """G.1 — concede o XP de esforço ao responder e devolve o resumo (xp ganho +
    conquistas novas + sequência) para o front celebrar. Best-effort e silencioso
    quando a gamificação está desligada."""
    try:
        from edubot.services.gamification import (register_daily_activity, award,
                                                  check_achievements, gamification_enabled)
        if not gamification_enabled():
            return None
        result = register_daily_activity(student.student_id)
        xp = result.get("xp", 0)
        achievements = list(result.get("achievements", []))
        # R.3 — desafio: responder uma questão DIFÍCIL (difficulty=3) de uma
        # competência DOMINADA é uma tentativa de desafio -> XP `desafio_tentado`
        # (dedup por questão/dia) + desbloqueia a conquista `desafiante`.
        cid = question.competency_id.competency_id
        if getattr(question, "difficulty", 2) == 3 and (mastery_map(student.student_id).get(cid) or 0) >= 0.8:
            xp += award(student.student_id, "desafio_tentado", "question", question.question_id)
        # quiz_do_modulo: respondeu todas as questões do OVA (independe da nota).
        if ova is not None:
            total_q = Questions.select().where(Questions.ova_id == ova.ova_id).count()
            attempted = (Attempts
                         .select(Questions.question_id)
                         .join(Questions, on=(Attempts.question_id == Questions.question_id))
                         .where((Attempts.student_id == student) &
                                (Questions.ova_id == ova.ova_id))
                         .distinct().count())
            if total_q and attempted >= total_q:
                xp += award(student.student_id, "quiz_do_modulo", "ova", ova.ova_id)
        achievements += check_achievements(student.student_id)
        return {"xp_awarded": xp, "achievements": achievements,
                "streak": result.get("streak", 0)}
    except Exception:
        return None

# Return all the questions from the database
@app_question.route("/question/all", methods=["GET"])
# Activate cross-origin to accept requests from another domain
@cross_origin()
# A.3: exige token. Antes a rota expunha TODO o banco de questões (sem gabarito,
# mas conteúdo pedagógico completo) a qualquer anônimo.
@require_auth
def show_all_questions():
    if request.method == "GET":
        try:
            # Get all the questions
            questions = Questions.select()
            question_list = []
            # For each question, append its id, statement and alternatives.
            # BUGFIX (B9): the correct answer is no longer sent to the client —
            # grading is done server-side in /question/answer.
            for question in questions:
                question_dict = {
                    "question_id": question.question_id,
                    "statement": question.statement,
                    "alternatives": _alternatives_list(question)
                }
                question_list.append(question_dict.copy())
            # Return the result array
            return json.dumps(question_list)
        except PeeweeException as err:
            # Handle the error by returning the description of the error
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return this if the HTTP method is not GET
        return "Wrong Request Methods. Only GET Allowed", 405

# Given an OVA, return all the questions of this OVA
@app_question.route("/question/ova", methods=["POST"])
# Activate cross-origin to accept requests from another domain
@cross_origin()
# A3/B4: exige token. Antes a rota aceitava student_id do payload e revelava
# quais questões QUALQUER aluno já tinha acertado. Agora o aluno vem do token.
@require_auth
def show_ova_questions():
    if request.method == "POST":
        try:
            question_data = get_payload()
            lang = get_lang()

            # U.1: gate de liberação — o quiz do módulo só abre após ler o
            # conteúdo (>= ova.quiz_gate_perc). Validado no backend: 403 com o
            # motivo estruturado ({gate, perc}) para o front explicar.
            ova = OVAs.get_or_none(OVAs.ova_id == question_data["ova_id"])
            if ova is None:
                return json.dumps({"Error": "Unknown ova_id"}), 400
            unlocked, info = quiz_unlocked(g.student, ova)
            if not unlocked:
                return json.dumps({"error": "quiz_locked", **info}), 403

            # Get all the questions of the given OVA
            questions = list(Questions.select().where(Questions.ova_id == question_data["ova_id"]))
            mastery_by_comp = mastery_map(g.student.student_id)
            if question_data.get("desafio"):
                # R.3 — modo desafio: só questões difíceis de competência dominada.
                # Sem material -> 403 challenge_locked (mesmo padrão do gate U.1).
                questions = challenge_pool(questions, mastery_by_comp)
                if not questions:
                    return json.dumps({"error": "challenge_locked"}), 403
            else:
                # D.4/B.5 — pool adaptativo: ordena/filtra por dificuldade vs. domínio
                # (mastery), com override por aluno (student_difficulty) quando existe.
                diff_overrides = difficulty_overrides_for(g.student.student_id)
                questions = adaptive_pool(questions, mastery_by_comp, diff_overrides)
            questions_ids = [question.question_id for question in questions]

            # Quais dessas questões o aluno LOGADO já acertou (do token, não do payload)
            answers_ids = Answers.select(Answers.question_id).where(Answers.student_id == g.student, Answers.question_id.in_(questions_ids))
            answers_ids = [id.question_id.question_id for id in answers_ids]

            question_list = []
            # For each question, append its id, statement, alternatives,
            # whether it was already answered, and the competency it works.
            # BUGFIX (B5/B9): the "answer" field (the correct alternative) used to be
            # shipped to the browser and rendered into a data-correct attribute,
            # exposing the answer key in the DOM. The quiz is now graded by the
            # backend (see /question/answer below).
            for question in questions:
                question_dict = {
                    "question_id": question.question_id,
                    "statement": tr(question.statement, question.statement_en, lang),
                    "alternatives": _alternatives_list(question, lang),
                    "answered": question.question_id in answers_ids,
                    "competency_id": question.competency_id.competency_id,
                    # D.4 — nível servido (o pool já foi filtrado/ordenado)
                    "difficulty": getattr(question, "difficulty", 2)
                }
                question_list.append(question_dict.copy())
            # Return the result array
            return json.dumps(question_list)
        except PeeweeException as err:
            # Handle the error by returning the description of the error
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return this if the HTTP method is not POST
        return "Wrong Request Methods. Only POST Allowed", 405

# Grades an answer sent by the student and records the attempt.
@app_question.route("/question/answer", methods=['POST'])
@cross_origin()
# A3: exige token. Antes gravava attempts em nome de QUALQUER student_id do
# payload (forjável anonimamente por curl), inflando a taxa_erro de outro aluno.
@require_auth
def answer_question():
    if request.method == 'POST':
        try:
            answer_data = get_payload()

            student = g.student  # A3: do token, não do payload
            question = Questions.select().where(Questions.question_id == answer_data["question_id"]).first()
            if question is None:
                return json.dumps({"Error": "Unknown question_id"}), 400

            # U.1: gate também na correção (defesa em profundidade) — não adianta
            # bloquear a listagem se o /answer aceitar respostas de quiz travado.
            ova = OVAs.get_or_none(OVAs.ova_id == question.ova_id)
            if ova is not None:
                unlocked, info = quiz_unlocked(student, ova)
                if not unlocked:
                    return json.dumps({"error": "quiz_locked", **info}), 403

            # BUGFIX (B5): grading used to happen in the browser (the client sent
            # an "is_correct" flag computed against a data-correct DOM attribute).
            # The selected alternative is now compared with the stored answer here,
            # so the answer key never leaves the server and the result can't be forged.
            selected = str(answer_data.get("selected", "")).strip().lower()
            is_correct = selected == str(question.answer).strip().lower()

            # A7 — idempotência: o front reenviava TODAS as questões a cada clique
            # em "Verificar", e cada clique gravava um Attempt novo (dois cliques =
            # tentativas em dobro, distorcendo a taxa_erro). Se o aluno já ACERTOU
            # esta questão (existe em `answers`) e reenvia a mesma resposta correta,
            # não registramos uma nova tentativa. Retentativas reais (mudar a
            # resposta / tentar de novo após errar) continuam contando.
            already_correct = Answers.select().where(
                Answers.question_id == question.question_id,
                Answers.student_id == student.student_id
            ).first()

            if not (is_correct and already_correct is not None):
                # IMPROVEMENT (Passo 3): tentativas (certas/erradas) alimentam a
                # regra do EduBot "errou mais de 50% do quiz".
                Attempts.create(
                    student_id = student,
                    question_id = question,
                    is_correct = is_correct
                )

            # Keep the original behavior: store the first correct answer in "answers"
            if is_correct and already_correct is None:
                Answers.create(
                    student_id = student,
                    question_id = question
                )

            # D.1 — evento xAPI-lite. `response_ms` é medido pelo front (do render
            # da questão ao submit) e mandado no payload; é o sinal de esforço que
            # o `interactions` não capturava. Só registra tentativas NOVAS (idem-
            # potência A7 acima).
            mastery_after = None
            if not (is_correct and already_correct is not None):
                emit_event(student, "answered", "question", question.question_id,
                           correct=is_correct,
                           response_ms=answer_data.get("response_ms"),
                           competency_id=question.competency_id.competency_id)
                # D.2 — atualiza o modelo do aluno (BKT) por competência. Síncrono
                # (1 upsert). Best-effort: nunca quebra a correção do quiz.
                try:
                    cid = question.competency_id.competency_id
                    mastery_after = update_on_attempt(student.student_id, cid, is_correct)
                    # D.3 — revisão espaçada: aplica o resultado a uma revisão
                    # vencida e agenda a 1ª revisão ao dominar a competência.
                    review_on_attempt(student.student_id, cid, is_correct, mastery_after)
                except Exception:
                    pass

            # A13 — proatividade por evento: um erro é o sinal de risco. O agente
            # avalia as regras do aluno na hora e, se for o caso, cria uma
            # intervenção/alerta automaticamente (o EduBot "fala primeiro"),
            # sem esperar o aluno clicar em "recomendação". Best-effort: nunca
            # quebra a correção do quiz.
            if not is_correct:
                trigger_evaluation(student, lang=get_lang(), trigger_type="quiz_failed")
                # Fase 4 (Plano de Rastreabilidade) — gatilho 1 do reforço: se o
                # domínio DESTA competência ficou abaixo do limiar, o aluno é
                # chamado para uma trilha focada nela (antes, o reforço só nascia
                # se ele fosse por conta própria à aba "Reforço").
                #
                # DEPOIS do trigger_evaluation de propósito: aquele guard pula a
                # avaliação quando já existe intervenção pendente do dia, então
                # criar a nossa antes silenciaria o agente proativo.
                suggest_reinforcement(
                    student.student_id, question.competency_id.competency_id,
                    question.competency_id.competency_description, mastery_after)

            # G.1 (Plano 2) — XP de ESFORÇO (best-effort, flag-guarded): responder
            # já é "dia de estudo"; completar TODAS as questões do módulo dá o XP
            # do quiz (independe da nota). Devolve o que ganhou p/ o micro-momento.
            gami = _gamify_answer(student, question, ova)

            # The frontend uses this flag to show "Correct!"/"Incorrect."
            return json.dumps({"is_correct": is_correct, "gamification": gami}), 200
        except PeeweeException as err:
            # Handle the error by returning the description of the error
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return this if the HTTP method is not POST
        return "Wrong Request Methods. Only POST Allowed", 405
