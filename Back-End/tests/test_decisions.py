"""B.2 — trilha de decisões do agente + estimativa de custo + guard de orçamento."""
import datetime
import json

from edubot.data.models.agent_decisions import AgentDecisions
from edubot.data.models.students import Students
from edubot.services import decisions


def test_estimate_cost_by_model():
    # Haiku: $1/$5 por 1M; Sonnet: $3/$15 por 1M (doc Anthropic).
    assert decisions.estimate_cost("claude-haiku-4-5", 1_000_000, 0) == 1.0
    assert decisions.estimate_cost("anthropic.claude-sonnet-4-6", 0, 1_000_000) == 15.0
    assert decisions.estimate_cost(None, 10, 10) == 0.0


def test_record_decision_persists(seeded_db):
    decisions.record_decision(
        Students.get_by_id(1), "on_demand",
        input_digest={"tipo": "trilha_minima"}, model_id="mock", mock=True,
        actions=[{"type": "intervention"}])
    row = AgentDecisions.get()
    assert row.trigger_type == "on_demand"
    assert row.mock is True
    assert row.input_digest["tipo"] == "trilha_minima"


def test_recommendation_records_decision(client, auth, seeded_db):
    before = AgentDecisions.select().count()
    r = client.get("/edubot/recommendation", headers=auth(1))
    assert r.status_code == 200
    assert AgentDecisions.select().count() == before + 1
    d = AgentDecisions.select().order_by(AgentDecisions.decision_id.desc()).get()
    assert d.trigger_type == "on_demand"
    # digest minimizado: não vaza RA nem nome completo
    assert "ra" not in d.input_digest and "nome" not in d.input_digest


def test_wrong_answer_records_event_decision(client, auth, seeded_db):
    client.post("/question/answer", headers=auth(1),
                data=json.dumps({"question_id": 1, "selected": "a"}))  # errada
    d = AgentDecisions.select().where(
        AgentDecisions.trigger_type == "quiz_failed").first()
    assert d is not None


def test_budget_exceeded(seeded_db):
    # Sem gasto real (só mock) -> nunca estoura.
    assert decisions.budget_exceeded(1.00) is False
    # Uma decisão real cara -> estoura um teto baixo.
    AgentDecisions.create(student_id=1, trigger_type="on_demand", mock=False,
                          model_id="claude-sonnet-4-6", input_tokens=1_000_000,
                          output_tokens=200_000, created_at=datetime.datetime.now())
    # custo ~ 3.0 + 3.0 = 6.0 USD
    assert decisions.spent_today_usd() >= 5.0
    assert decisions.budget_exceeded(1.00) is True
    assert decisions.budget_exceeded(0) is False   # teto 0 = desligado


def test_mock_decisions_not_counted_in_spend(seeded_db):
    AgentDecisions.create(student_id=1, trigger_type="on_demand", mock=True,
                          model_id="claude-sonnet-4-6", input_tokens=1_000_000,
                          output_tokens=1_000_000, created_at=datetime.datetime.now())
    assert decisions.spent_today_usd() == 0.0
