"""Proatividade do EduBot (A13) — o agente "fala primeiro".

Antes, o agente era 100% reativo: a recomendação só rodava no clique do aluno
(`/edubot/recommendation`) e a avaliação da turma só no clique do tutor
(`/tutor/evaluate`). Não havia gatilho por evento nem varredura agendada.

Este serviço centraliza a avaliação de UM aluno (perfil -> regras -> recomendação)
e a materializa como:
  - Intervenção (para o aluno ver no dashboard), deduplicada por tipo/dia;
  - Alerta (para o tutor), deduplicado por tipo enquanto não lido.

É chamado por gatilho de evento (pós-quiz/pós-conclusão de OVA) e pela varredura
agendada da turma. A regra decide QUANDO; a redação da mensagem já vem do agente
(mock determinístico ou LLM real via llm.py).
"""
import datetime
import logging

from edubot.agent import get_recommendation
from edubot.data.models.alerts import Alerts
from edubot.data.models.attempts import Attempts
from edubot.data.models.interactions import Interactions
from edubot.data.models.interventions import Interventions
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.students import Students
from edubot.services.student_context import build_student_profile
from edubot.services.decisions import record_decision, budget_exceeded
from edubot.services.events import emit
from edubot.services.consents import has_consent

logger = logging.getLogger("edubot.proactivity")

# Só materializa recomendações que valem a pena empurrar sem pedir.
ACTIONABLE_PRIORITIES = ("alta", "media")


def _last_tutor_questions(student, limit=3):
    """Últimas perguntas que o aluno levou ao tutor (D.1) — só as que têm texto
    (guardado sob consentimento). É o sinal que torna a intervenção específica."""
    from edubot.data.models.learning_events import LearningEvents
    sid = getattr(student, "student_id", student)
    perguntas = []
    for ev in (LearningEvents
               .select()
               .where((LearningEvents.student_id == sid) &
                      (LearningEvents.verb == "asked_tutor"))
               .order_by(LearningEvents.occurred_at.desc())
               .limit(limit)):
        texto = (ev.context or {}).get("text")
        if texto:
            perguntas.append(texto)
    return perguntas


def _redigir_para_caso(student, rec, profile, lang):
    """Chama o redator (Haiku) com um digest minimizado e enriquecido. Best-effort:
    devolve None em qualquer falha (o chamador usa o template)."""
    from edubot.agent.redactor import redigir_intervencao
    est = profile.get("estudante", {}) or {}
    comps = profile.get("competencias", [])
    fraca = None
    if comps:
        fraca = min(comps, key=lambda c: c.get("dominio_estimado")
                    if c.get("dominio_estimado") is not None else 1.0)
    # B.6 — histórico de outcomes: se as últimas intervenções foram dispensadas,
    # o redator é instruído a variar a abordagem.
    from edubot.services.outcomes import outcomes_summary
    # P.3 — o formato em que o aluno mais aprende e a que formato ele respondeu:
    # o redator propõe NO formato que funciona ("preparei um vídeo curto...").
    from edubot.services.preferences import learning_preference
    sid = getattr(student, "student_id", student)
    pref = learning_preference(sid, profile)
    digest = {
        "primeiro_nome": (est.get("nome") or "").split(" ")[0],
        "dias_sem_acesso": profile.get("dias_sem_acesso"),
        "percentual_consumido": profile.get("recursos", {}).get("percentual_consumido"),
        "taxa_erro_quiz": profile.get("quiz", {}).get("taxa_erro"),
        "competencia_mais_fraca": fraca["nome"] if fraca else None,
        "ultimas_perguntas_tutor": _last_tutor_questions(student),
        "historico_outcomes": outcomes_summary(sid),
        "formato_preferido": pref["formato"] if pref["confianca"] >= 0.4 else None,
        "respondeu_melhor_a": pref["respondeu_melhor_a"],
    }
    try:
        return redigir_intervencao(digest, rec, lang)
    except Exception:
        logger.exception("Falha ao redigir intervenção por caso")
        return None


def evaluate_student(student, *, create_alert=True, lang="pt", trigger_type="sweep"):
    """Avalia as regras do aluno e materializa a recomendação acionável.

    `lang` (Fase 4 — A12): idioma da mensagem da intervenção (o gatilho por
    evento usa o idioma da requisição do aluno; a varredura agendada usa PT).
    `trigger_type` (B.2): rótulo do que disparou a avaliação (sweep | quiz_failed
    | ova_completed) — registrado em agent_decisions.
    Retorna a recomendação criada (dict) ou None se nada acionável.
    Pode levantar exceção (use `trigger_evaluation` no caminho de escrita)."""
    profile = build_student_profile(student, lang=lang)
    # D.5: sem consentimento de IA sobre os dados, o agente roda só regras
    # (sem LLM) para este aluno.
    allow_llm = has_consent(student, "ia_sobre_dados")
    rec = get_recommendation(profile, lang=lang, allow_llm=allow_llm)

    # B.2 — trilha de decisão (mock incluído). Digest minimizado (sem RA/nome
    # completo): só primeiro nome + métricas que motivaram a decisão.
    est = profile.get("estudante", {})
    # B.6: baseline de domínio da competência-alvo (a mais fraca) — o job de
    # outcomes compara com o domínio atual para decidir se a intervenção
    # "melhorou" o aluno.
    comps = profile.get("competencias", [])
    alvo = min(comps, key=lambda c: c.get("dominio_estimado")
               if c.get("dominio_estimado") is not None else 1.0) if comps else None
    digest = {
        "primeiro_nome": (est.get("nome") or "").split(" ")[0],
        "dias_sem_acesso": profile.get("dias_sem_acesso"),
        "percentual_consumido": profile.get("recursos", {}).get("percentual_consumido"),
        "taxa_erro_quiz": profile.get("quiz", {}).get("taxa_erro"),
        "tipo": rec.get("tipo"),
        "prioridade": rec.get("prioridade"),
        "competencia_alvo_id": alvo["competency_id"] if alvo else None,
        "mastery_alvo": alvo.get("dominio_estimado") if alvo else None,
        # P.1/P.3 — em que formato a intervenção foi proposta. O job de outcomes
        # (B.6) marca o resultado; preferences._best_intervention_format cruza
        # formato × sucesso p/ descobrir a que formato o aluno responde.
        "formato_sugerido": rec.get("formato_preferido"),
    }
    acionavel = rec.get("prioridade") in ACTIONABLE_PRIORITIES
    record_decision(
        student, trigger_type, input_digest=digest,
        model_id=rec.get("model_id"), mock=rec.get("mock", True),
        actions=([{"type": "intervention", "tipo": rec.get("tipo")}] if acionavel else []))

    if not acionavel:
        return None

    # B.4 — a regra decidiu O QUÊ; o Haiku redige o COMO para o caso concreto.
    # Só quando há LLM real, orçamento (B.2), consentimento (D.5) e não é o sweep
    # em massa (que fica em template por custo — o top-N é tratado no chamador).
    # Template (rec["mensagem_aluno"]) é sempre o fallback.
    mensagem = rec["mensagem_aluno"]
    if allow_llm and trigger_type != "sweep" and not budget_exceeded():
        redigido = _redigir_para_caso(student, rec, profile, lang)
        if redigido:
            mensagem = redigido

    today = datetime.date.today()

    # Intervenção para o aluno — dedup por (aluno, tipo, dia) ainda pendente.
    has_intervention = (Interventions
                        .select()
                        .where((Interventions.student_id == student) &
                               (Interventions.date == today) &
                               (Interventions.type == rec["tipo"]) &
                               (Interventions.result == "pendente"))
                        .exists())
    if not has_intervention:
        created_it = Interventions.create(
            student_id=student, date=today, type=rec["tipo"],
            description=mensagem, result="pendente")
        # D.1 — o EduBot "falou primeiro": registra o evento de intervenção
        # recebida (matéria-prima do outcome em B.6 e da contagem por verbo).
        emit(student, "received_intervention", "intervention",
             created_it.intervention_id, tipo=rec["tipo"], trigger=trigger_type)

    # Alerta para o tutor — dedup por (aluno, tipo) enquanto não lido.
    if create_alert:
        has_alert = (Alerts
                     .select()
                     .where((Alerts.student_id == student) &
                            (Alerts.type == rec["tipo"]) &
                            (Alerts.read == False))
                     .exists())
        if not has_alert:
            Alerts.create(
                student_id=student, type=rec["tipo"],
                message=f"{student.student_name}: {rec['titulo']}",
                severity=rec["prioridade"],
                created_at=datetime.datetime.now(), read=False)

    return rec


def trigger_evaluation(student, lang="pt", trigger_type="event"):
    """Versão best-effort para o caminho de escrita (pós-quiz/progresso): nunca
    quebra a requisição principal se a avaliação falhar. Retorna a recomendação
    ou None.

    Guard de custo (A9): montar o perfil é caro (N+1); um quiz com N erros
    dispararia N avaliações na mesma submissão. Se o aluno já tem uma
    intervenção pendente criada HOJE, o gatilho por evento pula — ele já foi
    avisado; a varredura agendada e o /tutor/evaluate continuam avaliando
    por completo."""
    try:
        already_notified_today = (Interventions
                                  .select()
                                  .where((Interventions.student_id == student) &
                                         (Interventions.date == datetime.date.today()) &
                                         (Interventions.result == "pendente"))
                                  .exists())
        if already_notified_today:
            return None
        return evaluate_student(student, lang=lang, trigger_type=trigger_type)
    except Exception:
        logger.exception("Falha ao avaliar proatividade do aluno %s",
                         getattr(student, "student_id", "?"))
        return None


def active_student_ids():
    """IDs de alunos com ALGUMA atividade (interação, leitura ou tentativa).
    Fonte única usada pela varredura agendada e pelo painel do tutor — evita
    varrer os 500 alunos do seed e mantém a lógica em um só lugar (A15)."""
    ids = set()
    for query in (
        Interactions.select(Interactions.student_id).distinct().tuples(),
        OVAProgress.select(OVAProgress.student_id).distinct().tuples(),
        Attempts.select(Attempts.student_id).distinct().tuples(),
    ):
        for row in query:
            if row[0] is not None:
                ids.add(row[0])
    return ids


ALERT_EXPIRY_DAYS = 14


def expire_stale_alerts(days=ALERT_EXPIRY_DAYS):
    """A.4 — auto-expira alertas não lidos com mais de `days` dias.

    Higiene: sem isto, um alerta que o tutor nunca tratou fica aberto para sempre
    e — pela dedup por tipo — bloqueia novos alertas do mesmo tipo daquele aluno.
    Marcar como lido (read=True) após a validade libera a dedup e limpa o painel.
    Retorna quantos foram expirados."""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    return (Alerts
            .update(read=True)
            .where((Alerts.read == False) & (Alerts.created_at < cutoff))
            .execute())


def create_due_review_interventions(today=None):
    """D.3 — o sweep marca revisões vencidas e cria UMA intervenção por aluno
    ('hora de revisar X, Y'), deduplicada por dia. Retorna quantas criou."""
    from edubot.data.models.competencies import Competencies
    from edubot.data.models.review_schedule import ReviewSchedule
    from edubot.services.reviews import mark_due_reviews

    today = today or datetime.date.today()
    mark_due_reviews(today)

    # agrupa competências vencidas por aluno
    due_by_student = {}
    rows = (ReviewSchedule
            .select(ReviewSchedule.student_id, ReviewSchedule.competency_id)
            .where(ReviewSchedule.status == "vencida"))
    for r in rows:
        due_by_student.setdefault(r.student_id.student_id, []).append(r.competency_id.competency_id)

    created = 0
    for sid, comp_ids in due_by_student.items():
        has = (Interventions
               .select()
               .where((Interventions.student_id == sid) &
                      (Interventions.date == today) &
                      (Interventions.type == "revisao_espacada") &
                      (Interventions.result == "pendente"))
               .exists())
        if has:
            continue
        nomes = [c.competency_description for c in
                 Competencies.select().where(Competencies.competency_id.in_(comp_ids))]
        lista = ", ".join(nomes) if nomes else "seus tópicos em revisão"
        Interventions.create(
            student_id=sid, date=today, type="revisao_espacada",
            description=f"Hora de revisar: {lista}. Uma revisão curta agora consolida o que você já aprendeu.",
            result="pendente")
        emit(sid, "received_intervention", "intervention", None,
             tipo="revisao_espacada", trigger="review_sweep")
        created += 1
    return created


def create_weekly_goal_nudges(today=None):
    """E.3 — para cada aluno com atividade: sugere as metas da semana (idempotente)
    e, a partir de quinta-feira sem NENHUM progresso, cria uma intervenção de
    meio de semana (dedupada por dia). Retorna quantos nudges criou."""
    from edubot.services.gamification import gamification_enabled, _week_start
    from edubot.services.goals import suggest_weekly_goals, goals_state
    if not gamification_enabled():
        return 0
    today = today or datetime.date.today()
    week_start = _week_start(today)
    created = 0
    for sid in active_student_ids():
        try:
            goals = suggest_weekly_goals(sid, week_start)
        except Exception:
            logger.exception("Falha ao sugerir metas do aluno %s", sid)
            continue
        # nudge só de quinta (weekday 3) em diante e se o total ainda é zero
        if today.weekday() < 3 or not goals:
            continue
        total_progress = sum(g.get("progress", 0) if isinstance(g, dict) else g.progress
                             for g in goals_state(sid, week_start))
        if total_progress > 0:
            continue
        has = (Interventions
               .select()
               .where((Interventions.student_id == sid) &
                      (Interventions.date == today) &
                      (Interventions.type == "meta_semanal") &
                      (Interventions.result == "pendente"))
               .exists())
        if has:
            continue
        Interventions.create(
            student_id=sid, date=today, type="meta_semanal",
            description="Ainda dá tempo de cumprir suas metas desta semana! "
                        "Que tal 15 minutos de estudo agora?",
            result="pendente")
        emit(sid, "received_intervention", "intervention", None,
             tipo="meta_semanal", trigger="goal_nudge")
        created += 1
    return created


def run_class_evaluation(limit=200):
    """Varredura periódica (chamada pelo scheduler): avalia todos os alunos com
    atividade e materializa intervenções/alertas para quem entrou em risco —
    inclusive inatividade (Regra 1), pois um aluno que estudou e parou continua
    na lista. Também cobra as revisões espaçadas vencidas (D.3). Retorna quantas
    recomendações acionáveis foram criadas."""
    expire_stale_alerts()
    # H.1 (Plano 2) — snapshot diário do domínio (fundação das setas de tendência).
    try:
        from edubot.services.mastery import snapshot_today
        snapshot_today()
    except Exception:
        logger.exception("Falha ao gravar snapshot de mastery no sweep")
    # B.6 — o agente observa o efeito das próprias ações (classifica outcomes).
    try:
        from edubot.services.outcomes import compute_outcomes
        compute_outcomes()
    except Exception:
        logger.exception("Falha ao computar outcomes no sweep")
    created_reviews = create_due_review_interventions()
    # E.3 (Plano 2) — metas semanais: sugere (idempotente) e cobra no meio da
    # semana quem não engatou. Best-effort.
    try:
        create_weekly_goal_nudges()
    except Exception:
        logger.exception("Falha ao processar metas semanais no sweep")
    ids = list(active_student_ids())[:limit]
    if not ids:
        return created_reviews
    created = created_reviews
    for student in (Students
                    .select()
                    .where((Students.student_id.in_(ids)) &
                           (Students.role == "aluno"))):
        try:
            if evaluate_student(student) is not None:
                created += 1
        except Exception:
            logger.exception("Falha ao avaliar aluno %s na varredura", student.student_id)
    return created
