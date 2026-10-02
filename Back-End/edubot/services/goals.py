"""Metas semanais (E.3 — Plano 2).

O EduBot sugere 2 metas do tamanho do aluno toda segunda-feira; o aluno aceita
(1 clique); o progresso é DERIVADO dos mesmos sinais do XP (xp_events) — sem
telemetria nova. Cumprir concede o XP `meta_semanal` (uma vez). Uma meta por
(aluno, semana, tipo); a unique dá idempotência à sugestão.

Tudo best-effort e atrás da flag de gamificação (via gamification.award/enabled).
"""
import datetime
import logging

from edubot.data.models.weekly_goals import WeeklyGoals
from edubot.data.models.xp_events import XpEvents
from edubot.services.gamification import _week_start, award, gamification_enabled

logger = logging.getLogger("edubot.goals")

# tipo -> (rótulo pt, en, regra de XP que mede o progresso)
GOAL_KINDS = {
    "dias_de_estudo":   ("Estudar em {target} dias", "Study on {target} days", "dia_de_estudo"),
    "concluir_modulos": ("Concluir {target} módulo(s)", "Finish {target} module(s)", "modulo_concluido"),
    "revisoes_em_dia":  ("Fazer {target} revisão(ões) em dia", "Do {target} review(s) on time", "revisao_em_dia"),
}


def _count_rule_week(student_id, rule, week_start):
    """Progresso = nº de eventos de XP da regra na semana (dias_de_estudo é 1/dia,
    então o count já vira 'dias distintos')."""
    week_end = week_start + datetime.timedelta(days=6)
    return (XpEvents
            .select()
            .where((XpEvents.student_id == student_id) & (XpEvents.rule == rule) &
                   (XpEvents.awarded_on >= week_start) & (XpEvents.awarded_on <= week_end))
            .count())


def _suggested_targets(student_id, week_start):
    """Dimensiona as metas pela semana ANTERIOR (progressão suave, com pisos)."""
    prev = week_start - datetime.timedelta(days=7)
    dias_prev = _count_rule_week(student_id, "dia_de_estudo", prev)
    mod_prev = _count_rule_week(student_id, "modulo_concluido", prev)
    return {
        "dias_de_estudo": max(2, min(5, dias_prev + 1)),
        "concluir_modulos": max(1, min(3, mod_prev or 1)),
        "revisoes_em_dia": 2,
    }


def _has_active_reviews(student_id):
    from edubot.data.models.review_schedule import ReviewSchedule
    return (ReviewSchedule
            .select()
            .where((ReviewSchedule.student_id == student_id) &
                   (ReviewSchedule.status.in_(("agendada", "vencida"))))
            .exists())


def suggest_weekly_goals(student_id, week_start=None):
    """Cria (idempotente) as 2 metas sugeridas da semana: constância + 1 conforme
    o momento do aluno (revisar se há revisões ativas; senão, concluir módulos).
    Retorna as metas da semana."""
    if not gamification_enabled():
        return []
    week_start = week_start or _week_start()
    targets = _suggested_targets(student_id, week_start)
    second = "revisoes_em_dia" if _has_active_reviews(student_id) else "concluir_modulos"
    for kind in ("dias_de_estudo", second):
        existing = WeeklyGoals.get_or_none(
            (WeeklyGoals.student_id == student_id) &
            (WeeklyGoals.week_start == week_start) & (WeeklyGoals.kind == kind))
        if existing is None:
            WeeklyGoals.create(student_id=student_id, week_start=week_start, kind=kind,
                               target=targets[kind], progress=0, status="sugerida",
                               created_at=datetime.datetime.now())
    return recompute_progress(student_id, week_start)


def recompute_progress(student_id, week_start=None):
    """Atualiza o progresso das metas da semana pelos sinais de XP e conclui as
    que bateram a meta (concedendo meta_semanal 1×). Retorna a lista de metas."""
    week_start = week_start or _week_start()
    rows = list(WeeklyGoals
                .select()
                .where((WeeklyGoals.student_id == student_id) &
                       (WeeklyGoals.week_start == week_start)))
    for g in rows:
        rule = GOAL_KINDS.get(g.kind, (None, None, None))[2]
        if rule is None:
            continue
        g.progress = _count_rule_week(student_id, rule, week_start)
        if g.progress >= g.target and g.status in ("sugerida", "aceita"):
            g.status = "cumprida"
            # XP da meta cumprida (idempotente por objeto: goal_id)
            award(student_id, "meta_semanal", "goal", g.goal_id, today=datetime.date.today())
        g.save()
    return rows


def accept_goal(goal_id, student_id):
    """Aluno aceita a meta sugerida (sugerida -> aceita). Retorna a meta ou None."""
    g = WeeklyGoals.get_or_none((WeeklyGoals.goal_id == goal_id) &
                                (WeeklyGoals.student_id == student_id))
    if g is None:
        return None
    if g.status == "sugerida":
        g.status = "aceita"
        g.save()
    return g


def goals_state(student_id, week_start=None, lang="pt"):
    """Metas da semana (com progresso recalculado) para o front."""
    week_start = week_start or _week_start()
    rows = recompute_progress(student_id, week_start)
    out = []
    for g in rows:
        pt, en, _rule = GOAL_KINDS.get(g.kind, (g.kind, g.kind, None))
        label = (en if lang == "en" else pt).format(target=g.target)
        out.append({
            "goal_id": g.goal_id, "kind": g.kind, "titulo": label,
            "target": g.target, "progress": min(g.progress, g.target),
            "status": g.status,
        })
    return out
