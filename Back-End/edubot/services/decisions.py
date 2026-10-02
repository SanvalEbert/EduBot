"""Registro e observabilidade das decisões do agente (B.2).

Toda decisão do "cérebro" — mock ou LLM real — é registrada em `agent_decisions`
com custo/latência estimados. Serve auditabilidade (LGPD/explicabilidade),
observabilidade (dashboard do tutor) e, depois (B.6), o sinal de aprendizado
(`outcome`). Também expõe o guard de orçamento diário usado pelos caminhos de LLM.
"""
import datetime
import logging
import os

from edubot.data.models.agent_decisions import AgentDecisions

logger = logging.getLogger("edubot.decisions")

# Preços por 1M de tokens (USD) — input, output. Conferidos contra a doc atual
# da Anthropic/Bedrock (skill claude-api, cache 2026-06). Chave = substring do
# model_id (ex.: "anthropic.claude-sonnet-4-6" casa com "sonnet"). Ajuste aqui se
# a tabela de preços mudar; o mock tem custo zero.
MODEL_PRICES = {
    "haiku": (1.0, 5.0),
    "sonnet": (3.0, 15.0),
    "opus": (5.0, 25.0),
    "fable": (10.0, 50.0),
}
DEFAULT_PRICE = (3.0, 15.0)  # fallback tier-Sonnet

DAILY_BUDGET_USD = float(os.environ.get("EDUBOT_DAILY_BUDGET_USD", "1.00"))


def estimate_cost(model_id, input_tokens, output_tokens):
    """Custo estimado (USD) de uma chamada, pelos tokens e pelo modelo."""
    if not model_id:
        return 0.0
    price_in, price_out = DEFAULT_PRICE
    for key, prices in MODEL_PRICES.items():
        if key in model_id.lower():
            price_in, price_out = prices
            break
    return (input_tokens or 0) / 1e6 * price_in + (output_tokens or 0) / 1e6 * price_out


def record_decision(student, trigger_type, *, input_digest=None, model_id=None,
                    mock=True, tools_called=None, actions=None, latency_ms=0,
                    input_tokens=0, output_tokens=0):
    """Registra uma decisão. Best-effort: nunca quebra a requisição principal.

    `student` pode ser a linha Students ou um id (ou None). `input_digest` deve
    ser MINIMIZADO (sem RA/nome completo) — LGPD. Retorna a linha criada ou None."""
    try:
        sid = getattr(student, "student_id", student)
        return AgentDecisions.create(
            student_id=sid,
            trigger_type=trigger_type,
            input_digest=input_digest,
            model_id=model_id,
            mock=bool(mock),
            tools_called=tools_called,
            actions=actions,
            latency_ms=int(latency_ms or 0),
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            created_at=datetime.datetime.now(),
        )
    except Exception:
        logger.exception("Falha ao registrar decisão do agente (trigger=%s)", trigger_type)
        return None


def spent_today_usd(day=None):
    """Custo estimado somado das decisões (não-mock) de hoje."""
    day = day or datetime.date.today()
    start = datetime.datetime.combine(day, datetime.time.min)
    end = datetime.datetime.combine(day, datetime.time.max)
    total = 0.0
    for d in (AgentDecisions
              .select(AgentDecisions.model_id, AgentDecisions.input_tokens,
                      AgentDecisions.output_tokens)
              .where((AgentDecisions.created_at >= start) &
                     (AgentDecisions.created_at <= end) &
                     (AgentDecisions.mock == False))):
        total += estimate_cost(d.model_id, d.input_tokens, d.output_tokens)
    return round(total, 4)


def budget_exceeded(daily_budget_usd=None):
    """True se o custo estimado de hoje já atingiu o teto diário (B.4/B.5 usam
    isto para degradar os caminhos de LLM para template)."""
    budget = DAILY_BUDGET_USD if daily_budget_usd is None else daily_budget_usd
    if budget <= 0:
        return False
    return spent_today_usd() >= budget
