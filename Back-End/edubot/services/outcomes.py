"""Outcome das decisões do agente (B.6) — o EduBot observa o efeito do que fez.

Job diário: para cada `agent_decisions` com `outcome IS NULL` e idade >= 2 dias,
classifica o resultado a partir dos eventos de aprendizado (D.1) e do domínio
(D.2) posteriores à decisão:

  melhorou   — o domínio da competência-alvo subiu >= MASTERY_GAIN (0.1) desde a
               decisão (usa a baseline `mastery_alvo` gravada no digest);
  aceita     — o aluno voltou a estudar (opened/answered/played/read/completed)
               em ATÉ 7 dias após a decisão;
  dispensada — houve `dismissed` da intervenção e NENHUM engajamento em 7 dias;
  expirada   — nada em 14 dias.

É o sinal de aprendizado do agente: o resumo dos outcomes recentes entra no
digest do redator (B.4) — o modelo é instruído a variar a abordagem quando o
histórico mostra rejeição — e vira o KPI do painel do tutor.
"""
import datetime
import logging

from edubot.data.models.agent_decisions import AgentDecisions
from edubot.data.models.learning_events import LearningEvents

logger = logging.getLogger("edubot.outcomes")

MIN_AGE_DAYS = 2          # tempo mínimo p/ o aluno reagir antes de classificar
EXPIRE_DAYS = 14          # sem sinal até aqui -> expirada
ENGAGE_WINDOW_DAYS = 7    # janela p/ considerar "voltou a estudar"
MASTERY_GAIN = 0.10       # ganho de domínio p/ "melhorou"

ENGAGE_VERBS = ("opened", "answered", "played", "read", "completed")


def _classify(decision, now):
    """Decide o outcome de UMA decisão, ou None se ainda indefinido (na janela)."""
    created = decision.created_at
    age_days = (now - created).days
    if age_days < MIN_AGE_DAYS:
        return None

    sid = decision.student_id.student_id if decision.student_id else None
    if sid is None:
        return "expirada" if age_days >= EXPIRE_DAYS else None

    window_end = created + datetime.timedelta(days=ENGAGE_WINDOW_DAYS)
    engaged = (LearningEvents
               .select()
               .where((LearningEvents.student_id == sid) &
                      (LearningEvents.verb.in_(ENGAGE_VERBS)) &
                      (LearningEvents.occurred_at > created) &
                      (LearningEvents.occurred_at <= window_end))
               .exists())
    dismissed = (LearningEvents
                 .select()
                 .where((LearningEvents.student_id == sid) &
                        (LearningEvents.verb == "dismissed") &
                        (LearningEvents.occurred_at > created))
                 .exists())

    # melhorou (tem precedência): domínio da competência-alvo subiu.
    digest = decision.input_digest or {}
    cid = digest.get("competencia_alvo_id")
    baseline = digest.get("mastery_alvo")
    if cid is not None and baseline is not None:
        from edubot.services.mastery import mastery_map
        atual = mastery_map(sid).get(cid)
        if atual is not None and (atual - baseline) >= MASTERY_GAIN:
            return "melhorou"

    if engaged:
        return "aceita"
    if dismissed:
        return "dispensada"
    if age_days >= EXPIRE_DAYS:
        return "expirada"
    return None


def compute_outcomes(now=None, lookback_days=30):
    """Classifica as decisões pendentes. Retorna quantas foram resolvidas."""
    now = now or datetime.datetime.now()
    floor = now - datetime.timedelta(days=lookback_days)
    resolved = 0
    for decision in (AgentDecisions
                     .select()
                     .where((AgentDecisions.outcome.is_null()) &
                            (AgentDecisions.created_at >= floor) &
                            (AgentDecisions.created_at <= now - datetime.timedelta(days=MIN_AGE_DAYS)))):
        outcome = _classify(decision, now)
        if outcome:
            decision.outcome = outcome
            decision.save()
            resolved += 1
    logger.info("Outcomes computados: %s decisões resolvidas.", resolved)
    return resolved


def outcomes_summary(student_id, days=30):
    """{outcome: contagem} das decisões recentes do aluno — alimenta o digest do
    redator (B.4) e a leitura do agente. Inclui `pendente` (outcome ainda nulo)."""
    from peewee import fn
    since = datetime.datetime.now() - datetime.timedelta(days=days)
    summary = {}
    rows = (AgentDecisions
            .select(AgentDecisions.outcome, fn.COUNT(AgentDecisions.decision_id).alias("n"))
            .where((AgentDecisions.student_id == student_id) &
                   (AgentDecisions.created_at >= since))
            .group_by(AgentDecisions.outcome))
    for r in rows:
        summary[r.outcome or "pendente"] = r.n
    return summary
