"""Revisão espaçada (D.3) — SM-2 simplificado sobre `review_schedule`.

Cada (aluno, competência) tem no máximo UMA revisão ativa (agendada|vencida) que
avança no tempo:
  - domínio (D.2) cruza 0.8 para cima  -> agenda a 1ª revisão em REVIEW_FIRST_DAYS;
  - acerto numa questão da competência NA DATA ou depois -> intervalo × ease
    (teto REVIEW_MAX_DAYS), reagenda;
  - erro -> intervalo volta a 1 dia e ease -= 0.2 (piso EASE_MIN);
  - o sweep diário marca as vencidas e cria a intervenção "hora de revisar X".

`schedule` é idempotente (reusa a revisão ativa); tudo best-effort no caminho de
escrita do quiz (nunca quebra a correção).
"""
import datetime
import logging

from edubot.data.models.review_schedule import ReviewSchedule

logger = logging.getLogger("edubot.reviews")

REVIEW_FIRST_DAYS = 3       # 1ª revisão após dominar a competência
REVIEW_MAX_DAYS = 60        # teto do intervalo
EASE_MIN = 1.3
EASE_STEP = 0.2
MASTERY_REVIEW_THRESHOLD = 0.8

ACTIVE_STATUSES = ("agendada", "vencida")


def _active(student_id, competency_id):
    return (ReviewSchedule
            .select()
            .where((ReviewSchedule.student_id == student_id) &
                   (ReviewSchedule.competency_id == competency_id) &
                   (ReviewSchedule.status.in_(ACTIVE_STATUSES)))
            .order_by(ReviewSchedule.due_date)
            .first())


def schedule(student_id, competency_id, days_from_now=REVIEW_FIRST_DAYS,
             created_by="agent", today=None):
    """Cria ou reagenda a revisão ativa da competência. Idempotente: se já existe
    uma revisão ativa, apenas move a data. Retorna a linha."""
    today = today or datetime.date.today()
    due = today + datetime.timedelta(days=max(1, days_from_now))
    row = _active(student_id, competency_id)
    if row is not None:
        row.due_date = due
        row.interval_days = max(1, days_from_now)
        row.status = "agendada"
        row.save()
        return row
    return ReviewSchedule.create(
        student_id=student_id, competency_id=competency_id, due_date=due,
        interval_days=max(1, days_from_now), ease=2.5, status="agendada",
        created_by=created_by, created_at=datetime.datetime.now())


def register_result(student_id, competency_id, is_correct, today=None):
    """Aplica o resultado de uma questão à revisão ativa, SE ela está vencida/no
    prazo (due_date <= hoje). Fora da data, não altera o agendamento. Retorna a
    linha atualizada ou None."""
    today = today or datetime.date.today()
    row = _active(student_id, competency_id)
    if row is None or row.due_date > today:
        return None
    if is_correct:
        row.interval_days = min(REVIEW_MAX_DAYS, max(1, round(row.interval_days * row.ease)))
    else:
        row.ease = max(EASE_MIN, row.ease - EASE_STEP)
        row.interval_days = 1
    row.due_date = today + datetime.timedelta(days=row.interval_days)
    row.status = "agendada"
    row.save()
    return row


def on_attempt(student_id, competency_id, is_correct, p_mastery, today=None):
    """Orquestra o gancho de revisão no caminho do quiz. Best-effort.

    1) aplica o resultado a uma revisão vencida/no prazo (register_result);
    2) se o domínio cruzou o limiar e não há revisão ativa, agenda a 1ª revisão."""
    try:
        applied = register_result(student_id, competency_id, is_correct, today=today)
        # G.1 (Plano 2) — revisar EM DIA é esforço: concede XP (idempotente por
        # competência/dia). `applied` != None => a revisão estava vencida/no prazo.
        if applied is not None:
            from edubot.services.gamification import award
            award(student_id, "revisao_em_dia", "competency", competency_id, today=today)
            # Fase 4 (Plano de Rastreabilidade) — gatilho 3 do reforço: errar a
            # revisão é o sinal mais forte de que o conteúdo não consolidou. O
            # `ease` já caiu no register_result; quando ele chega ao piso, o
            # aluno vem errando de forma reincidente e merece uma trilha nova.
            if not is_correct and applied.ease <= EASE_MIN:
                from edubot.data.models.competencies import Competencies
                from edubot.services.reinforcement import suggest_reinforcement
                comp = Competencies.get_or_none(Competencies.competency_id == competency_id)
                suggest_reinforcement(
                    student_id, competency_id,
                    comp.competency_description if comp else None,
                    p_mastery, today=today)
        if (p_mastery is not None and p_mastery >= MASTERY_REVIEW_THRESHOLD
                and _active(student_id, competency_id) is None):
            schedule(student_id, competency_id, REVIEW_FIRST_DAYS,
                     created_by="rule", today=today)
    except Exception:
        logger.exception("Falha no gancho de revisão (aluno=%s comp=%s)",
                         student_id, competency_id)


def mark_due_reviews(today=None):
    """Marca como 'vencida' as revisões 'agendada' com due_date <= hoje. Retorna
    quantas foram marcadas (usado pelo sweep)."""
    today = today or datetime.date.today()
    return (ReviewSchedule
            .update(status="vencida")
            .where((ReviewSchedule.status == "agendada") &
                   (ReviewSchedule.due_date <= today))
            .execute())


def due_reviews(student_id, today=None, horizon_days=7):
    """Revisões vencidas + as que vencem nos próximos `horizon_days` dias, para o
    aluno (alimenta a agenda 'Revisões desta semana' e a intervenção)."""
    today = today or datetime.date.today()
    limit_date = today + datetime.timedelta(days=horizon_days)
    return list(ReviewSchedule
                .select()
                .where((ReviewSchedule.student_id == student_id) &
                       (ReviewSchedule.status.in_(ACTIVE_STATUSES)) &
                       (ReviewSchedule.due_date <= limit_date))
                .order_by(ReviewSchedule.due_date))
