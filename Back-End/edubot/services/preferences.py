"""Preferência de aprendizagem do aluno (P.1 — Plano 2).

Responde "COMO este aluno aprende melhor?" a partir de sinais que JÁ existem no
banco — sem tabela nova:

  1. Conclusão por formato  — taxa `concluidos/total` de `consumption_by_type`
     (vídeo/texto/podcast). É sinal mais forte que a contagem de CONSUMO usada
     antes (começar um vídeo != aprender com ele).
  2. Resposta às intervenções — cruza `agent_decisions.input_digest.formato_sugerido`
     com o `outcome` (aceita/melhorou = sucesso): a que formato de SUGESTÃO o
     aluno respondeu (o B.6 vira sensor de preferência).
  3. Dificuldade confortável — em qual nível de `questions.difficulty` o aluno
     tem a melhor razão acerto/tentativa.

Degradação segura é o default: sem sinal suficiente (`confianca < CONFIDENT`),
os consumidores tratam como "sem preferência" — o comportamento atual. Nada aqui
entra no caminho de `/student/me` (o perfil segue em <= 8 queries): quando o
`profile` é passado, reusa `consumption_by_type` sem query extra.
"""
import datetime

from peewee import Case, fn

from edubot.data.models.agent_decisions import AgentDecisions
from edubot.data.models.attempts import Attempts
from edubot.data.models.questions import Questions

FORMATS = ("video", "texto", "podcast")
# Nº de conclusões p/ confiar na preferência (2 conclusões -> confianca 0.5).
_CONFIDENCE_DIVISOR = 4.0
CONFIDENT = 0.4          # abaixo disto, "sem preferência" (degradação segura)
_INTERVENTION_LOOKBACK_DAYS = 60
_SUCCESS_OUTCOMES = ("aceita", "melhorou")


def _consumption_by_type(student_id, profile):
    """`{formato: {total, consumidos, concluidos}}` — do profile (grátis) ou
    montado (constrói o perfil só quando chamado fora do caminho do agente)."""
    if profile is None:
        from edubot.data.models.students import Students
        from edubot.services.student_context import build_student_profile
        profile = build_student_profile(Students.get_by_id(student_id))
    return (profile.get("recursos", {}) or {}).get("por_tipo", {}) or {}


def _best_intervention_format(student_id):
    """Formato de SUGESTÃO ao qual o aluno melhor respondeu (aceita/melhorou),
    ou None. Processa em Python (JSONField não é portável de consultar entre
    SQLite/MySQL) — mesmo padrão do outcomes.py. Retorna (formato, taxa)."""
    since = datetime.datetime.now() - datetime.timedelta(days=_INTERVENTION_LOOKBACK_DAYS)
    tally = {}   # formato -> [sucessos, total_classificado]
    for d in (AgentDecisions
              .select(AgentDecisions.input_digest, AgentDecisions.outcome)
              .where((AgentDecisions.student_id == student_id) &
                     (AgentDecisions.created_at >= since) &
                     (AgentDecisions.outcome.is_null(False)))):
        fmt = (d.input_digest or {}).get("formato_sugerido")
        if fmt not in FORMATS:
            continue
        slot = tally.setdefault(fmt, [0, 0])
        slot[1] += 1
        if d.outcome in _SUCCESS_OUTCOMES:
            slot[0] += 1
    best = None
    for fmt, (ok, total) in tally.items():
        if total == 0:
            continue
        rate = ok / total
        if best is None or rate > best[1]:
            best = (fmt, round(rate, 2))
    return best if best else (None, None)


def _comfortable_difficulty(student_id):
    """Nível de dificuldade (1..3) com a melhor razão de acerto (>= 2 tentativas
    no nível), ou None. 1 query agregada (attempts x questions.difficulty)."""
    rows = (Attempts
            .select(Questions.difficulty.alias("difficulty"),
                    fn.COUNT(Attempts.attempt_id).alias("total"),
                    fn.SUM(Case(None, [(Attempts.is_correct == True, 1)], 0)).alias("acertos"))
            .join(Questions, on=(Attempts.question_id == Questions.question_id))
            .where(Attempts.student_id == student_id)
            .group_by(Questions.difficulty)
            .dicts())
    best = None
    for r in rows:
        total = r["total"] or 0
        if total < 2:
            continue
        ratio = (r["acertos"] or 0) / total
        level = r["difficulty"] or 2
        if best is None or ratio > best[1]:
            best = (level, ratio)
    return best[0] if best else None


def learning_preference(student_id, profile=None):
    """Modelo de preferência do aluno. Ver docstring do módulo.

    Retorna dict com: formato, formato_fallback, confianca (0..1),
    taxa_conclusao_por_formato, respondeu_melhor_a, dificuldade_confortavel.
    `formato` é None (e confianca 0) quando não há sinal suficiente — os
    consumidores devem checar `confianca >= CONFIDENT` antes de personalizar."""
    cbt = _consumption_by_type(student_id, profile)

    rates = {}
    total_concluidos = 0
    for fmt in FORMATS:
        stats = cbt.get(fmt)
        if stats and stats.get("total"):
            concluidos = stats.get("concluidos", 0) or 0
            rates[fmt] = round(concluidos / stats["total"], 2)
            total_concluidos += concluidos

    respondeu, _resp_taxa = _best_intervention_format(student_id)

    # Formato preferido: maior taxa de conclusão; desempate por nº de conclusões
    # e, ainda empatado, pelo formato ao qual respondeu melhor nas intervenções.
    formato = formato_fallback = None
    if rates:
        ordered = sorted(
            rates.items(),
            key=lambda kv: (-kv[1],
                            -((cbt.get(kv[0]) or {}).get("concluidos", 0) or 0),
                            0 if kv[0] == respondeu else 1))
        formato = ordered[0][0]
        formato_fallback = ordered[1][0] if len(ordered) > 1 else None

    confianca = round(min(1.0, total_concluidos / _CONFIDENCE_DIVISOR), 2)

    return {
        "formato": formato,
        "formato_fallback": formato_fallback,
        "confianca": confianca,
        "taxa_conclusao_por_formato": rates,
        "respondeu_melhor_a": respondeu,
        "dificuldade_confortavel": _comfortable_difficulty(student_id),
    }


def preferred_format(student_id, profile=None):
    """Atalho: o formato preferido SÓ quando há confiança suficiente, senão None.
    É o que P.2/P.3 usam para decidir se personalizam a ordem da trilha."""
    pref = learning_preference(student_id, profile)
    if pref["formato"] and pref["confianca"] >= CONFIDENT:
        return pref["formato"]
    return None
