"""B.6 — outcome das decisões do agente (o EduBot observa o efeito)."""
import datetime
import json

from edubot.data.models.agent_decisions import AgentDecisions
from edubot.data.models.learning_events import LearningEvents
from edubot.data.models.student_mastery import StudentMastery
from edubot.services import outcomes as O

NOW = datetime.datetime(2026, 6, 1, 12, 0, 0)


def _decision(days_ago, digest=None, outcome=None):
    return AgentDecisions.create(
        student_id=1, trigger_type="quiz_failed", input_digest=digest or {},
        mock=True, created_at=NOW - datetime.timedelta(days=days_ago), outcome=outcome)


def _event(verb, days_ago, object_type="ova"):
    LearningEvents.create(student_id=1, verb=verb, object_type=object_type,
                          occurred_at=NOW - datetime.timedelta(days=days_ago))


def test_aceita_when_engaged_within_window(seeded_db):
    _decision(days_ago=3)
    _event("opened", days_ago=2)  # voltou a estudar 1 dia depois
    assert O.compute_outcomes(now=NOW) == 1
    assert AgentDecisions.select().first().outcome == "aceita"


def test_dispensada_when_dismissed_without_engagement(seeded_db):
    _decision(days_ago=5)
    _event("dismissed", days_ago=4, object_type="intervention")
    O.compute_outcomes(now=NOW)
    assert AgentDecisions.select().first().outcome == "dispensada"


def test_melhorou_when_mastery_rose(seeded_db):
    _decision(days_ago=5, digest={"competencia_alvo_id": 1, "mastery_alvo": 0.3})
    StudentMastery.create(student_id=1, competency_id=1, p_mastery=0.5,
                          attempts_seen=3, updated_at=NOW)
    O.compute_outcomes(now=NOW)
    assert AgentDecisions.select().first().outcome == "melhorou"


def test_expirada_when_nothing_in_14_days(seeded_db):
    _decision(days_ago=15)
    O.compute_outcomes(now=NOW)
    assert AgentDecisions.select().first().outcome == "expirada"


def test_too_young_stays_pending(seeded_db):
    _decision(days_ago=1)
    assert O.compute_outcomes(now=NOW) == 0
    assert AgentDecisions.select().first().outcome is None


def test_idempotent_does_not_reclassify(seeded_db):
    _decision(days_ago=3)
    _event("opened", days_ago=2)
    O.compute_outcomes(now=NOW)
    # segunda passada: já resolvida -> não reprocessa
    assert O.compute_outcomes(now=NOW) == 0


# outcomes_summary/tool/kpi consultam a janela relativa ao AGORA real, então
# usam datas recentes (não o NOW fixo dos testes de classificação).
def _recent_decision(days_ago, digest=None, outcome=None):
    return AgentDecisions.create(
        student_id=1, trigger_type="quiz_failed", input_digest=digest or {},
        mock=True, created_at=datetime.datetime.now() - datetime.timedelta(days=days_ago),
        outcome=outcome)


def test_outcomes_summary(seeded_db):
    _recent_decision(days_ago=3, outcome="aceita")
    _recent_decision(days_ago=4, outcome="dispensada")
    _recent_decision(days_ago=5, outcome="dispensada")
    s = O.outcomes_summary(1)
    assert s["aceita"] == 1 and s["dispensada"] == 2


def test_historico_intervencoes_tool(seeded_db):
    from edubot.agent import tools as T
    from edubot.data.models.students import Students
    _recent_decision(days_ago=3, digest={"tipo": "trilha_minima"}, outcome="dispensada")
    r = T.execute_tool("historico_intervencoes", {}, {"student": Students.get_by_id(1)})
    assert r["resumo"].get("dispensada") == 1
    assert r["ultimas"][0]["outcome"] == "dispensada"


def test_agent_kpi_route(client, auth, seeded_db):
    _recent_decision(days_ago=3, digest={"tipo": "trilha_minima"}, outcome="aceita")
    _recent_decision(days_ago=4, digest={"tipo": "trilha_minima"}, outcome="dispensada")
    _recent_decision(days_ago=5, digest={"tipo": "trilha_minima"}, outcome="melhorou")
    resp = client.get("/tutor/agent-kpi", headers=auth(9))  # tutor
    assert resp.status_code == 200
    kpi = [k for k in json.loads(resp.data)["kpis"] if k["tipo"] == "trilha_minima"][0]
    # 3 classificadas, 2 sucesso (aceita+melhorou) -> 0.67
    assert kpi["taxa_aceitacao"] == 0.67
    assert kpi["total"] == 3


def test_agent_kpi_by_format(client, auth, seeded_db):
    # P.3 — recorte por formato SUGERIDO: vídeo aceito, texto dispensado.
    _recent_decision(days_ago=3, digest={"formato_sugerido": "video"}, outcome="aceita")
    _recent_decision(days_ago=4, digest={"formato_sugerido": "video"}, outcome="melhorou")
    _recent_decision(days_ago=5, digest={"formato_sugerido": "texto"}, outcome="dispensada")
    resp = client.get("/tutor/agent-kpi", headers=auth(9))
    por_formato = {k["formato"]: k for k in json.loads(resp.data)["kpis_por_formato"]}
    assert por_formato["video"]["taxa_aceitacao"] == 1.0
    assert por_formato["texto"]["taxa_aceitacao"] == 0.0
