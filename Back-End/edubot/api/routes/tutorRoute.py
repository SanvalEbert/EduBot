# MELHORIA (Roteiro Cena 4) — Painel do Tutor + Central de Alertas.
#
#   GET  /tutor/turma     -> alunos (com atividade) do curso do tutor + KPIs
#   GET  /tutor/alerts    -> alertas preventivos da turma
#   POST /tutor/evaluate  -> roda as regras do EduBot sobre a turma, gerando
#                            intervenções e alertas para alunos em risco
#
# Todas exigem token (@require_auth) E papel de tutor/admin (g.student.role).
from flask import Blueprint, g
from flask_cors import cross_origin
from peewee import Case, JOIN, PeeweeException, fn
import json

from edubot.data.models.students import Students
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.attempts import Attempts
from edubot.data.models.alerts import Alerts
from edubot.data.models.competencies import Competencies
from edubot.data.models.subjects import Subjects
from edubot.data.models.offerings import Offerings
from edubot.data.models.student_mastery import StudentMastery
# Plano 5 (17.4): modelos usados só no rollup do gestor (/tutor/overview).
from edubot.data.models.answers import Answers
from edubot.data.models.questions import Questions
from edubot.data.models.interactions import Interactions
from edubot.data.models.learning_events import LearningEvents
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.ova_section_progress import OVASectionProgress
from edubot.data.models.resources import Resources
from edubot.data.models.ovas import OVAs
from edubot.data.models.consents import Consents

from edubot.api.auth import require_auth, is_staff
from edubot.api.http import get_lang, get_payload
from edubot.i18n import tr
from edubot.data.models.review_schedule import ReviewSchedule
from edubot.services.coverage import coverage_gaps
from edubot.services.risk import compute_risk
from edubot.services.mastery import (status_from_mastery, mastery_trend,
                                     DEVELOPING_THRESHOLD, DEVELOPED_THRESHOLD)
from edubot.services.proactivity import evaluate_student, active_student_ids
# A15: inatividade vem da fonte única (multi-sinal). A cópia local antiga só
# olhava `interactions` — um aluno que lia e respondia quiz todo dia aparecia
# como "inativo" no painel do tutor.
# Plano 5 (17.3): build_student_profile monta o perfil detalhado de UM aluno
# para o professor — mesmo shape de /student/me, reuso total da lógica de métrica.
from edubot.services.student_context import _days_without_access, build_student_profile

app_tutor = Blueprint("tutor", __name__)

# Máximo de alunos avaliados por requisição (proteção: o curso de exemplo tem 500)
MAX_TURMA = 60


def _is_tutor():
    # A15/A.3: papel de gestão vem da fonte única (edubot.api.auth.is_staff).
    return is_staff(g.student)


def _turma_students():
    course_id = g.student.course_id
    active = active_student_ids()  # fonte única (edubot.services.proactivity)
    if not active:
        return []
    query = (Students
             .select()
             .where((Students.course_id == course_id) &
                    (Students.student_id.in_(list(active))) &
                    (Students.role == "aluno"))
             .limit(MAX_TURMA))
    return list(query)


def _student_summary(student):
    consumo = (OVAProgress
               .select(fn.AVG(OVAProgress.perc_scrolled))
               .where(OVAProgress.student_id == student)
               .scalar())
    total = Attempts.select().where(Attempts.student_id == student).count()
    wrong = (Attempts
             .select()
             .where((Attempts.student_id == student) & (Attempts.is_correct == False))
             .count())
    abertos = (Alerts
               .select()
               .where((Alerts.student_id == student) & (Alerts.read == False))
               .count())

    dias = _days_without_access(student)
    consumo_perc = int(consumo) if consumo is not None else 0
    taxa_erro = round(wrong / total, 2) if total else None

    # Fase 3 — risco COMPOSTO. O critério anterior (taxa_erro > 0.5) não via o
    # aluno que sumiu (quem não tenta não erra) nem o que está esquecendo.
    vencidas = (ReviewSchedule
                .select()
                .where((ReviewSchedule.student_id == student) &
                       (ReviewSchedule.status == "vencida"))
                .count())
    caindo = sum(1 for t in mastery_trend(student.student_id).values()
                 if t["direcao"] == "down")
    risco = compute_risk(taxa_erro=taxa_erro, dias_sem_acesso=dias,
                         revisoes_vencidas=vencidas, consumo_perc=consumo_perc,
                         tendencia_queda=caindo)

    return {
        "student_id": student.student_id,
        "nome": student.student_name,
        "ra": student.ra,
        "dias_sem_acesso": dias,
        "consumo_percentual": consumo_perc,
        "taxa_erro": taxa_erro,
        "alertas_abertos": abertos,
        "revisoes_vencidas": vencidas,
        # `componentes`/`principal` explicam POR QUE o aluno está em risco — sem
        # isso o professor recebe um número e nenhuma pista de como agir.
        "risco": risco,
    }


@app_tutor.route("/tutor/turma", methods=["GET"])
@cross_origin()
@require_auth
def tutor_turma():
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        alunos = [_student_summary(s) for s in _turma_students()]
        # ordena por mais críticos primeiro (mais alertas, depois menos consumo)
        alunos.sort(key=lambda a: (-a["alertas_abertos"], a["consumo_percentual"]))
        return json.dumps({"total": len(alunos), "alunos": alunos}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_tutor.route("/tutor/alerts", methods=["GET"])
@cross_origin()
@require_auth
def tutor_alerts():
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        course_id = g.student.course_id
        rows = (Alerts
                .select(Alerts, Students)
                .join(Students)
                .where((Students.course_id == course_id) &
                       # B.5: itens da fila de aprovação vivem em /tutor/queue,
                       # não poluem a central de alertas informativos.
                       (Alerts.status != "aguardando_aprovacao"))
                .order_by(Alerts.created_at.desc())
                .limit(50))
        out = [{
            "alert_id": a.alert_id,
            "student_id": a.student_id.student_id,
            "aluno": a.student_id.student_name,
            "type": a.type,
            "message": a.message,
            "severity": a.severity,
            "created_at": str(a.created_at),
            "read": bool(a.read),
        } for a in rows]
        return json.dumps({"alertas": out}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# A.4 — marca um alerta como TRATADO (read=True).
#
# Sem isto, a dedup de alertas ("por tipo enquanto não lido", em
# proactivity.evaluate_student) congelava: o primeiro alerta de cada tipo ficava
# aberto para sempre e SUPRIMIA todos os futuros do mesmo tipo daquele aluno — a
# central de alertas do tutor parava de crescer após o primeiro dia.
@app_tutor.route("/tutor/alert/ack", methods=["POST"])
@cross_origin()
@require_auth
def tutor_alert_ack():
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        data = get_payload()
        alert_id = data.get("alert_id")
        # Só alertas de alunos do curso do tutor (não vaza/edita outra turma).
        alert = (Alerts
                 .select(Alerts, Students)
                 .join(Students)
                 .where((Alerts.alert_id == alert_id) &
                        (Students.course_id == g.student.course_id))
                 .first())
        if alert is None:
            return json.dumps({"Error": "Alerta não encontrado"}), 404
        alert.read = True
        alert.save()
        return json.dumps({"ok": True, "alert_id": alert_id}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_tutor.route("/tutor/mastery", methods=["GET"])
@cross_origin()
@require_auth
def tutor_mastery():
    """D.6 — heatmap turma × competência a partir de `student_mastery`.

    Devolve, para o curso do tutor:
      - `competencias`: por competência, média de domínio e distribuição
        (frágil / em desenvolvimento / desenvolvida) — o KPI da turma;
      - `matriz`: linha por aluno (com atividade) e célula por competência com
        o domínio estimado — o grid colorido do painel."""
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        lang = get_lang()
        course_id = g.student.course_id

        # Competências do curso (colunas do heatmap), ordenadas POR ASSUNTO para o
        # front conseguir agrupar as colunas por disciplina (Plano 5).
        comps = list(Competencies
                     .select(Competencies.competency_id,
                             Competencies.competency_description,
                             Competencies.competency_description_en,
                             Subjects.subject_id.alias("subject_id"),
                             Subjects.subject_name.alias("subject_nome"))
                     .join(Subjects, on=(Competencies.subject_id == Subjects.subject_id))
                     .join(Offerings, on=(Offerings.subject_id == Subjects.subject_id))
                     .where(Offerings.course_id == course_id)
                     .order_by(Subjects.subject_id, Competencies.competency_id)
                     .distinct()
                     .dicts())
        comp_meta = [{"competency_id": c["competency_id"],
                      "subject_id": c["subject_id"],
                      "subject_nome": c["subject_nome"],
                      "nome": tr(c["competency_description"], c["competency_description_en"], lang)}
                     for c in comps]

        # Mastery da turma (1 query): student_mastery ∩ alunos do curso.
        # .dicts() devolve os ids crus das FKs (evita ambiguidade do join).
        rows = (StudentMastery
                .select(StudentMastery.student_id.alias("student_id"),
                        StudentMastery.competency_id.alias("competency_id"),
                        StudentMastery.p_mastery.alias("p_mastery"),
                        Students.student_name.alias("nome"))
                .join(Students, on=(StudentMastery.student_id == Students.student_id))
                .where((Students.course_id == course_id) & (Students.role == "aluno"))
                .dicts())

        by_student = {}      # sid -> {nome, celulas:{cid:p}}
        by_comp = {}         # cid -> [p, ...]
        for r in rows:
            sid = r["student_id"]
            cid = r["competency_id"]
            p = r["p_mastery"]
            st = by_student.setdefault(sid, {"student_id": sid,
                                             "nome": r["nome"], "celulas": {}})
            st["celulas"][cid] = round(p, 2)
            by_comp.setdefault(cid, []).append(p)

        for c in comp_meta:
            vals = by_comp.get(c["competency_id"], [])
            c["n"] = len(vals)
            c["media"] = round(sum(vals) / len(vals), 2) if vals else None
            c["distribuicao"] = {
                "fragil": sum(1 for v in vals if v < DEVELOPING_THRESHOLD),
                "em_desenvolvimento": sum(1 for v in vals
                                          if DEVELOPING_THRESHOLD <= v < DEVELOPED_THRESHOLD),
                "desenvolvida": sum(1 for v in vals if v >= DEVELOPED_THRESHOLD),
            }

        matriz = [{
            "student_id": s["student_id"],
            "nome": s["nome"],
            "celulas": [{"competency_id": c["competency_id"],
                         "p_mastery": s["celulas"].get(c["competency_id"]),
                         "status": status_from_mastery(s["celulas"].get(c["competency_id"]))}
                        for c in comp_meta],
        } for s in sorted(by_student.values(), key=lambda x: x["nome"])]

        return json.dumps({"competencias": comp_meta, "matriz": matriz}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# ---------------------------------------------------------------------------
# B.5 — Fila de aprovação: ações de tier alto do agente esperam o tutor.
# ---------------------------------------------------------------------------
def _execute_proposed_action(alert):
    """Executa a `proposed_action` de um item da fila ao ser aprovado. Hoje:
    intervenção assinada 'do seu tutor'. Retorna um resumo do que foi feito."""
    import datetime
    from edubot.data.models.interventions import Interventions
    from edubot.services.events import emit

    action = alert.proposed_action or {}
    if action.get("type") == "intervencao_do_tutor":
        it = Interventions.create(
            student_id=alert.student_id, date=datetime.date.today(),
            type="mensagem_tutor", description=action.get("mensagem_aluno", ""),
            result="pendente")
        emit(alert.student_id, "received_intervention", "intervention",
             it.intervention_id, tipo="mensagem_tutor", trigger="tutor_approval")
        return {"intervention_id": it.intervention_id}
    return {}


def _queue_alert(alert_id):
    """Item da fila (aguardando_aprovacao) do curso do tutor, ou None."""
    return (Alerts
            .select(Alerts, Students)
            .join(Students)
            .where((Alerts.alert_id == alert_id) &
                   (Students.course_id == g.student.course_id) &
                   (Alerts.status == "aguardando_aprovacao"))
            .first())


@app_tutor.route("/tutor/queue", methods=["GET"])
@cross_origin()
@require_auth
def tutor_queue():
    """Ações propostas pelo EduBot que aguardam aprovação do tutor (B.5)."""
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        rows = (Alerts
                .select(Alerts, Students)
                .join(Students)
                .where((Students.course_id == g.student.course_id) &
                       (Alerts.status == "aguardando_aprovacao"))
                .order_by(Alerts.created_at.desc())
                .limit(50))
        out = [{
            "alert_id": a.alert_id,
            "student_id": a.student_id.student_id,
            "aluno": a.student_id.student_name,
            "type": a.type,
            "message": a.message,
            "severity": a.severity,
            "proposed_action": a.proposed_action,
            "created_at": str(a.created_at),
        } for a in rows]
        return json.dumps({"fila": out}, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_tutor.route("/tutor/queue/approve", methods=["POST"])
@cross_origin()
@require_auth
def tutor_queue_approve():
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        alert = _queue_alert(get_payload().get("alert_id"))
        if alert is None:
            # 404 também se já foi tratado (idempotência: aprova UMA vez).
            return json.dumps({"Error": "Item da fila não encontrado ou já tratado"}), 404
        done = _execute_proposed_action(alert)
        alert.status = "aprovado"
        alert.read = True
        alert.save()
        _set_decision_outcome(alert.decision_id, "aceita")
        return json.dumps({"ok": True, "alert_id": alert.alert_id, "executado": done}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_tutor.route("/tutor/queue/reject", methods=["POST"])
@cross_origin()
@require_auth
def tutor_queue_reject():
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        alert = _queue_alert(get_payload().get("alert_id"))
        if alert is None:
            return json.dumps({"Error": "Item da fila não encontrado ou já tratado"}), 404
        alert.status = "rejeitado"
        alert.read = True
        alert.save()
        _set_decision_outcome(alert.decision_id, "dispensada")
        return json.dumps({"ok": True, "alert_id": alert.alert_id}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


def _set_decision_outcome(decision_id, outcome):
    """Marca o outcome da decisão do agente ligada ao item (B.6). No-op se não há
    decisão vinculada."""
    if not decision_id:
        return
    from edubot.data.models.agent_decisions import AgentDecisions
    (AgentDecisions
     .update(outcome=outcome)
     .where(AgentDecisions.decision_id == decision_id)
     .execute())


@app_tutor.route("/tutor/agent-kpi", methods=["GET"])
@cross_origin()
@require_auth
def tutor_agent_kpi():
    """B.6 — KPI do agente: taxa de aceitação das intervenções por tipo, na
    turma do tutor (últimos 60 dias). aceita/melhorou contam como sucesso."""
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        import datetime
        from edubot.data.models.agent_decisions import AgentDecisions

        since = datetime.datetime.now() - datetime.timedelta(days=60)
        # decisões dos alunos do curso do tutor (join p/ filtrar por curso).
        rows = (AgentDecisions
                .select(AgentDecisions.input_digest, AgentDecisions.trigger_type,
                        AgentDecisions.outcome)
                .join(Students, on=(AgentDecisions.student_id == Students.student_id))
                .where((Students.course_id == g.student.course_id) &
                       (AgentDecisions.created_at >= since))
                .dicts())

        SUCCESS = ("aceita", "melhorou")

        def _new_bucket(chave, valor):
            return {chave: valor, "total": 0, "classificadas": 0, "aceita": 0,
                    "melhorou": 0, "dispensada": 0, "expirada": 0, "pendente": 0}

        def _finalize(buckets, chave):
            out = []
            for b in buckets.values():
                sucesso = b["aceita"] + b["melhorou"]
                b["taxa_aceitacao"] = round(sucesso / b["classificadas"], 2) \
                    if b["classificadas"] else None
                out.append(b)
            out.sort(key=lambda x: (-(x["taxa_aceitacao"] or -1), -x["total"]))
            return out

        by_type = {}
        by_format = {}   # P.3 — taxa de aceitação × formato SUGERIDO
        for r in rows:
            digest = r["input_digest"] or {}
            outcome = r["outcome"] or "pendente"
            tipo = digest.get("tipo") or r["trigger_type"] or "outro"
            b = by_type.setdefault(tipo, _new_bucket("tipo", tipo))
            b["total"] += 1
            b[outcome] = b.get(outcome, 0) + 1
            if outcome != "pendente":
                b["classificadas"] += 1

            formato = digest.get("formato_sugerido")
            if formato:
                f = by_format.setdefault(formato, _new_bucket("formato", formato))
                f["total"] += 1
                f[outcome] = f.get(outcome, 0) + 1
                if outcome != "pendente":
                    f["classificadas"] += 1

        return json.dumps({"kpis": _finalize(by_type, "tipo"),
                           "kpis_por_formato": _finalize(by_format, "formato")},
                          default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_tutor.route("/tutor/engagement", methods=["GET"])
@cross_origin()
@require_auth
def tutor_engagement():
    """E.4 (Plano 2) — engajamento da turma: participação no ranking, distribuição
    de sequências, XP médio da semana, alunos prestes a perder a sequência, e a
    validação ANTES×DEPOIS da gamificação (dias ativos/aluno em duas janelas)."""
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        import datetime
        from edubot.data.models.consents import Consents
        from edubot.data.models.learning_events import LearningEvents
        from edubot.services.gamification import streak_state, xp_week

        alunos = _turma_students()
        today = datetime.date.today()
        ids = [s.student_id for s in alunos]
        n = len(alunos)

        # participação no ranking (opt-in)
        opt_in = 0
        if ids:
            opt_in = (Consents.select()
                      .where((Consents.student_id.in_(ids)) &
                             (Consents.purpose == "ranking_turma") &
                             (Consents.granted == True)).count())

        # distribuição de sequências + XP médio + em risco
        dist = {"0": 0, "1-2": 0, "3-6": 0, "7+": 0}
        soma_xp = 0
        em_risco = []
        for s in alunos:
            st = streak_state(s.student_id, today)
            d = st["current_days"]
            bucket = "0" if d == 0 else "1-2" if d <= 2 else "3-6" if d <= 6 else "7+"
            dist[bucket] += 1
            soma_xp += xp_week(s.student_id)
            # estudou ONTEM e ainda não hoje -> quebra amanhã se não voltar
            from edubot.data.models.student_streak import StudentStreak
            row = StudentStreak.get_or_none(StudentStreak.student_id == s.student_id)
            if row and row.last_activity_date == today - datetime.timedelta(days=1) and d > 0:
                em_risco.append({"student_id": s.student_id, "nome": s.student_name,
                                 "sequencia": d})

        # validação antes×depois: dias ativos distintos por aluno em 2 janelas de 28d.
        # AUDITORIA P2: DISTINCT sobre occurred_at (DATETIME) contava TIMESTAMPS
        # (cada evento é quase único) — inflava a métrica para "nº de eventos".
        # COUNT(DISTINCT DATE(...)) conta DIAS de verdade (DATE() existe em
        # MySQL e SQLite).
        def _active_days_avg(start, end):
            if not ids:
                return 0.0
            total_days = 0
            for sid in ids:
                total_days += (LearningEvents
                               .select(fn.COUNT(fn.DATE(LearningEvents.occurred_at).distinct()))
                               .where((LearningEvents.student_id == sid) &
                                      (LearningEvents.occurred_at >= start) &
                                      (LearningEvents.occurred_at < end))
                               .scalar()) or 0
            return round(total_days / len(ids), 2)

        win = datetime.timedelta(days=28)
        now = datetime.datetime.now()
        depois = _active_days_avg(now - win, now)
        antes = _active_days_avg(now - 2 * win, now - win)

        # EX.4 (Plano 3) — uso do companheiro de estudo, tudo de learning_events
        # (verbos de CP.2/CP.4/CP.5), sem migration. O tutor enxerga se o
        # personagem está sendo usado ou ignorado — critério honesto p/ manter/ajustar.
        week_start = now - datetime.timedelta(days=7)

        def _count(verb, obj_type=None, start=week_start):
            if not ids:
                return 0
            q = (LearningEvents
                 .select()
                 .where((LearningEvents.student_id.in_(ids)) &
                        (LearningEvents.verb == verb) &
                        (LearningEvents.occurred_at >= start)))
            if obj_type:
                q = q.where(LearningEvents.object_type == obj_type)
            return q.count()

        def _distinct_students(verb, start):
            if not ids:
                return 0
            return (LearningEvents
                    .select(fn.COUNT(LearningEvents.student_id.distinct()))
                    .where((LearningEvents.student_id.in_(ids)) &
                           (LearningEvents.verb == verb) &
                           (LearningEvents.occurred_at >= start))
                    .scalar()) or 0

        companheiro = {
            "alunos_ativos": _distinct_students("companion_spoke", now - win),  # 28d
            "total_alunos": n,
            "secoes_ouvidas_semana": _count("played", "ova_section"),   # CP.5
            "falas_ouvidas_semana": _count("companion_listened"),        # CP.2 (▶ no balão)
            "explicacoes_semana": _count("companion_explain"),           # CP.4
        }

        return json.dumps({
            "total_alunos": n,
            "participacao_ranking": {"opt_in": opt_in, "total": n},
            "distribuicao_sequencia": dist,
            "xp_medio_semana": round(soma_xp / n, 1) if n else 0,
            "em_risco": em_risco,
            "antes_depois": {"dias_ativos_antes": antes, "dias_ativos_depois": depois},
            "companheiro": companheiro,
        }, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_tutor.route("/tutor/evaluate", methods=["POST"])
@cross_origin()
@require_auth
def tutor_evaluate():
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        # Mesma avaliação usada pelos gatilhos por evento (fonte única): perfil
        # -> regras -> intervenção/alerta deduplicados. Aqui varre a turma.
        criados = 0
        for student in _turma_students():
            if evaluate_student(student) is not None:
                criados += 1
        return json.dumps({"alertas_criados": criados}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


@app_tutor.route("/tutor/student/<int:student_id>", methods=["GET"])
@cross_origin()
@require_auth
def tutor_student_detail(student_id):
    """Plano 5 (17.3) — perfil DETALHADO de um aluno, para o professor.

    Reusa `build_student_profile` (mesmo contrato de /student/me), então o front
    reaproveita os componentes de desempenho do aluno para montar o detalhe
    (gráficos + números brutos por competência e por assunto).

    Segurança: só devolve aluno com `role="aluno"` do MESMO curso do tutor. Fora
    disso responde 404 — não vaza a existência de alunos de outras turmas. O
    filtro é feito no SQL (não confia no front que só mostra o link para staff)."""
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        student = (Students
                   .select()
                   .where((Students.student_id == student_id) &
                          (Students.course_id == g.student.course_id) &
                          (Students.role == "aluno"))
                   .first())
        if student is None:
            return json.dumps({"Error": "Aluno não encontrado nesta turma."}), 404
        return json.dumps(build_student_profile(student, lang=get_lang()), default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# Quantas seções "mais difíceis" o painel mostra. O professor age sobre poucas;
# uma lista longa vira ruído.
HARD_SECTIONS_LIMIT = 8


def _hard_sections(sids):
    """Fase 2 — "onde a turma trava": seções com maior tempo médio de leitura e
    releitura. Uma agregação SQL sobre ova_section_progress (sem N+1).

    O sinal é o par (tempo médio, releituras): uma seção onde muita gente volta
    e demora é uma seção que não está ensinando bem — exatamente o que o
    rastreio do OVA inteiro não conseguia apontar."""
    rows = (OVASectionProgress
            .select(OVASectionProgress.ova_id,
                    OVASectionProgress.section_id,
                    OVASectionProgress.section_index,
                    OVAs.ova_name.alias("ova_nome"),
                    fn.COUNT(OVASectionProgress.section_progress_id).alias("alunos"),
                    fn.AVG(OVASectionProgress.active_seconds).alias("segundos_medios"),
                    fn.SUM(OVASectionProgress.visits).alias("visitas"))
            .join(OVAs, on=(OVASectionProgress.ova_id == OVAs.ova_id))
            .where(OVASectionProgress.student_id.in_(sids))
            .group_by(OVASectionProgress.ova_id, OVASectionProgress.section_id,
                      OVASectionProgress.section_index, OVAs.ova_name)
            .dicts())

    secoes = []
    for r in rows:
        alunos = r["alunos"] or 0
        visitas = int(r["visitas"] or 0)
        secoes.append({
            "ova_id": r["ova_id"],
            "ova_nome": r["ova_nome"],
            "section_id": r["section_id"],
            "section_index": r["section_index"],
            "alunos": alunos,
            "segundos_medios": int(r["segundos_medios"] or 0),
            # > 1 significa que, em média, os alunos voltaram à seção.
            "releituras_por_aluno": round(visitas / alunos, 2) if alunos else 0,
        })
    secoes.sort(key=lambda s: (s["segundos_medios"], s["releituras_por_aluno"]), reverse=True)
    return secoes[:HARD_SECTIONS_LIMIT]


def _video_stats(sids):
    """Fase 1 — consumo REAL de vídeo da turma.

    `cobertura_media` é a fração da linha do tempo efetivamente percorrida (não a
    posição alcançada) e `ponto_abandono_medio` diz onde a turma larga o vídeo."""
    row = (ResourceProgress
           .select(fn.AVG(ResourceProgress.coverage_perc).alias("cobertura"),
                   fn.SUM(ResourceProgress.watched_seconds).alias("segundos"),
                   fn.AVG(ResourceProgress.last_position_seconds).alias("abandono"))
           .join(Resources, on=(ResourceProgress.resource_id == Resources.resource_id))
           .where((ResourceProgress.student_id.in_(sids)) &
                  (Resources.resource_type == "video"))
           .dicts().get())
    return {
        "cobertura_media": int(row["cobertura"] or 0),
        "segundos_assistidos": int(row["segundos"] or 0),
        "ponto_abandono_medio": int(row["abandono"]) if row["abandono"] is not None else None,
    }


@app_tutor.route("/tutor/overview", methods=["GET"])
@cross_origin()
@require_auth
def tutor_overview():
    """Plano 5 (17.4) — rollup da turma para o painel do GESTOR.

    Mostra "tudo que o sistema consegue medir" da turma: totais de quiz,
    acertos/erros POR ASSUNTO (disciplina), consumo médio e um catálogo de quanto
    de cada sinal já está registrado. Tudo em agregações SQL — NÃO monta
    build_student_profile por aluno (o curso de exemplo tem 500)."""
    if not _is_tutor():
        return json.dumps({"Error": "Acesso restrito a tutores."}), 403
    try:
        course = g.student.course_id
        course_id = course.course_id if course else None
        sids = [s.student_id for s in _turma_students()]
        n_alunos = len(sids)

        if not sids:
            return json.dumps({
                "turma": {"alunos_ativos": 0, "em_risco": 0, "alertas_abertos": 0},
                "quiz": {"acertos": 0, "erros": 0, "tentativas": 0, "taxa_erro": None},
                "consumo": {"percentual_medio": 0},
                "por_assunto": [],
                "rastreamento": {},
            }, default=str), 200

        # --- Totais de quiz da turma (2 queries) -----------------------------
        att = (Attempts
               .select(fn.COUNT(Attempts.attempt_id).alias("tentativas"),
                       fn.SUM(Case(None, [(Attempts.is_correct == False, 1)], 0)).alias("erros"))
               .where(Attempts.student_id.in_(sids))
               .dicts().get())
        tentativas = att["tentativas"] or 0
        erros = int(att["erros"] or 0)
        acertos = (Answers
                   .select(fn.COUNT(Answers.answer_id))
                   .where(Answers.student_id.in_(sids))
                   .scalar()) or 0
        taxa_erro = round(erros / tentativas, 2) if tentativas else None

        # --- Em risco: score COMPOSTO (Fase 3), a MESMA regra do painel do
        # professor — duas definições de "risco" na mesma plataforma seria pior
        # do que uma definição imperfeita. Ter um alerta aberto NÃO conta como
        # risco (um alerta pode ser positivo, ex.: "aprofundamento"); alertas têm
        # KPI próprio.
        alertas_abertos = (Alerts
                           .select(fn.COUNT(Alerts.alert_id))
                           .where((Alerts.student_id.in_(sids)) & (Alerts.read == False))
                           .scalar()) or 0
        risco = {s.student_id for s in _turma_students()
                 if _student_summary(s)["risco"]["em_risco"]}

        # --- Por assunto (disciplina) ----------------------------------------
        # Base: todos os assuntos do curso + total de questões (nível curso, para
        # a cobertura aparecer mesmo em assunto sem nenhuma tentativa).
        by_subject = {}
        for r in (Subjects
                  .select(Subjects.subject_id, Subjects.subject_name,
                          fn.COUNT(Questions.question_id.distinct()).alias("total_q"))
                  .join(Offerings, on=(Offerings.subject_id == Subjects.subject_id))
                  .switch(Subjects)
                  .join(Competencies, JOIN.LEFT_OUTER,
                        on=(Competencies.subject_id == Subjects.subject_id))
                  .join(Questions, JOIN.LEFT_OUTER,
                        on=(Questions.competency_id == Competencies.competency_id))
                  .where(Offerings.course_id == course_id)
                  .group_by(Subjects.subject_id)
                  .order_by(Subjects.subject_id)
                  .dicts()):
            by_subject[r["subject_id"]] = {
                "subject_id": r["subject_id"],
                "subject_nome": r["subject_name"],
                "acertos": 0, "erros": 0, "tentativas": 0,
                "total_questoes": r["total_q"] or 0,
                "taxa_erro": None, "dominio_medio": None,
            }

        # acertos por assunto (Answers é ≤1 por (aluno,questão) — sem fan-out)
        for r in (Answers
                  .select(Subjects.subject_id.alias("sid"),
                          fn.COUNT(Answers.answer_id).alias("c"))
                  .join(Questions, on=(Answers.question_id == Questions.question_id))
                  .join(Competencies, on=(Questions.competency_id == Competencies.competency_id))
                  .join(Subjects, on=(Competencies.subject_id == Subjects.subject_id))
                  .where(Answers.student_id.in_(sids))
                  .group_by(Subjects.subject_id).dicts()):
            if r["sid"] in by_subject:
                by_subject[r["sid"]]["acertos"] = r["c"] or 0

        # tentativas/erros por assunto
        for r in (Attempts
                  .select(Subjects.subject_id.alias("sid"),
                          fn.COUNT(Attempts.attempt_id).alias("t"),
                          fn.SUM(Case(None, [(Attempts.is_correct == False, 1)], 0)).alias("w"))
                  .join(Questions, on=(Attempts.question_id == Questions.question_id))
                  .join(Competencies, on=(Questions.competency_id == Competencies.competency_id))
                  .join(Subjects, on=(Competencies.subject_id == Subjects.subject_id))
                  .where(Attempts.student_id.in_(sids))
                  .group_by(Subjects.subject_id).dicts()):
            if r["sid"] in by_subject:
                by_subject[r["sid"]]["tentativas"] = r["t"] or 0
                by_subject[r["sid"]]["erros"] = int(r["w"] or 0)

        # domínio médio (BKT) por assunto
        for r in (StudentMastery
                  .select(Subjects.subject_id.alias("sid"),
                          fn.AVG(StudentMastery.p_mastery).alias("m"))
                  .join(Competencies, on=(StudentMastery.competency_id == Competencies.competency_id))
                  .join(Subjects, on=(Competencies.subject_id == Subjects.subject_id))
                  .where(StudentMastery.student_id.in_(sids))
                  .group_by(Subjects.subject_id).dicts()):
            if r["sid"] in by_subject and r["m"] is not None:
                by_subject[r["sid"]]["dominio_medio"] = round(r["m"], 2)

        for s in by_subject.values():
            s["taxa_erro"] = round(s["erros"] / s["tentativas"], 2) if s["tentativas"] else None
        por_assunto = sorted(by_subject.values(), key=lambda x: x["subject_id"])

        # --- Consumo médio de leitura (proxy honesto já usado no painel) ------
        consumo = (OVAProgress
                   .select(fn.AVG(OVAProgress.perc_scrolled))
                   .where(OVAProgress.student_id.in_(sids))
                   .scalar())
        consumo_medio = int(consumo) if consumo is not None else 0

        # --- Catálogo: quanto de cada sinal está registrado hoje --------------
        def _count(model, pk):
            return (model.select(fn.COUNT(pk)).where(model.student_id.in_(sids)).scalar()) or 0

        rastreamento = {
            "interacoes": _count(Interactions, Interactions.interaction_id),
            "ova_progress": _count(OVAProgress, OVAProgress.progress_id),
            "progresso_recursos": _count(ResourceProgress, ResourceProgress.resource_progress_id),
            "tentativas_quiz": tentativas,
            "eventos_aprendizado": _count(LearningEvents, LearningEvents.event_id),
            "consentimentos": _count(Consents, Consents.consent_id),
            "linhas_mastery": _count(StudentMastery, StudentMastery.student_id),
            # Fase 2 — leitura por seção do OVA (o "onde travou").
            "leitura_por_secao": _count(OVASectionProgress, OVASectionProgress.section_progress_id),
        }

        return json.dumps({
            "turma": {"alunos_ativos": n_alunos, "em_risco": len(risco), "alertas_abertos": alertas_abertos},
            "quiz": {"acertos": acertos, "erros": erros, "tentativas": tentativas, "taxa_erro": taxa_erro},
            "consumo": {"percentual_medio": consumo_medio},
            "por_assunto": por_assunto,
            "secoes_dificeis": _hard_sections(sids),
            "video": _video_stats(sids),
            # Fase 4 (§6.2): competências que o reforço NÃO consegue atender bem
            # (poucas questões ou formato único). É lacuna de conteúdo, e o
            # gestor é quem pode resolvê-la.
            "lacunas_conteudo": coverage_gaps(course_id),
            "rastreamento": rastreamento,
        }, default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
