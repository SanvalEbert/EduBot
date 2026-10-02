"""B.5 — ajustar_dificuldade + alertar_tutor + fila de aprovação do tutor."""
import datetime
import json

from edubot.agent import tools as T
from edubot.data.models.alerts import Alerts
from edubot.data.models.interventions import Interventions
from edubot.data.models.questions import Questions
from edubot.data.models.student_difficulty import StudentDifficulty
from edubot.data.models.students import Students


def _ctx(sid=1):
    return {"student": Students.get_by_id(sid)}


# --- ajustar_dificuldade ---------------------------------------------------
def test_ajustar_dificuldade_sets_and_caps(seeded_db):
    r = T.execute_tool("ajustar_dificuldade", {"competency_id": 1, "delta": 1}, _ctx())
    assert r["level"] == 3          # 2 (default) + 1
    # segunda mudança no mesmo dia é barrada (teto 1/dia)
    r2 = T.execute_tool("ajustar_dificuldade", {"competency_id": 1, "delta": -1}, _ctx())
    assert "error" in r2


def test_ajustar_dificuldade_clamps_and_validates(seeded_db):
    # delta inválido
    assert "error" in T.execute_tool("ajustar_dificuldade", {"competency_id": 1, "delta": 2}, _ctx())
    # competência de fora do curso
    assert "error" in T.execute_tool("ajustar_dificuldade", {"competency_id": 999, "delta": 1}, _ctx())


def test_override_affects_question_pool(client, auth, seeded_db):
    # questão difícil na comp 1
    Questions.create(question_id=3, statement="dificil",
                     alternatives={"alternatives": ["a", "b"]}, answer="a",
                     ova_id=1, competency_id=1, difficulty=3)
    # sem override e sem mastery -> difícil excluída
    resp = client.post("/question/ova", data=json.dumps({"ova_id": 1}), headers=auth())
    assert 3 not in [q["question_id"] for q in json.loads(resp.data)]
    # override level 3 -> teto min(3, 3+1)=3 -> difícil aparece
    StudentDifficulty.create(student_id=1, competency_id=1, level=3,
                             updated_at=datetime.datetime.now())
    resp2 = client.post("/question/ova", data=json.dumps({"ova_id": 1}), headers=auth())
    assert 3 in [q["question_id"] for q in json.loads(resp2.data)]


# --- alertar_tutor ---------------------------------------------------------
def test_alertar_tutor_media_is_open(seeded_db):
    r = T.execute_tool("alertar_tutor",
                       {"tipo": "risco", "mensagem": "atenção", "severidade": "media"}, _ctx())
    a = Alerts.get_by_id(r["alert_id"])
    assert a.status == "aberto"


def test_alertar_tutor_alta_goes_to_queue(seeded_db):
    r = T.execute_tool("alertar_tutor",
                       {"tipo": "evasao", "mensagem": "risco alto", "severidade": "alta"}, _ctx())
    a = Alerts.get_by_id(r["alert_id"])
    assert a.status == "aguardando_aprovacao"


# --- propor_mensagem_do_tutor (tier queue) ---------------------------------
def test_propor_mensagem_never_creates_intervention_directly(seeded_db):
    r = T.execute_tool("propor_mensagem_do_tutor",
                       {"mensagem_aluno": "Vamos marcar uma conversa?"}, _ctx())
    assert r["queued"] is True
    # NADA visível ao aluno até a aprovação
    assert Interventions.select().count() == 0
    a = Alerts.get_by_id(r["alert_id"])
    assert a.status == "aguardando_aprovacao"
    assert a.proposed_action["type"] == "intervencao_do_tutor"


def test_propor_mensagem_dedup_while_pending(seeded_db):
    # AUDITORIA E1-6: enquanto houver proposta pendente do aluno, chamadas
    # repetidas do agente NÃO empilham novas na fila do tutor.
    r1 = T.execute_tool("propor_mensagem_do_tutor", {"mensagem_aluno": "Oi!"}, _ctx())
    r2 = T.execute_tool("propor_mensagem_do_tutor", {"mensagem_aluno": "Oi de novo!"}, _ctx())
    assert r2["alert_id"] == r1["alert_id"] and r2.get("dedup") is True
    assert Alerts.select().where(Alerts.type == "mensagem_proposta").count() == 1


def test_queue_item_linked_to_decision_and_outcome(client, auth, seeded_db):
    # AUDITORIA E1-6 (B.5/B.6): o item de fila criado numa execução do agente
    # fica LIGADO à decisão (alerts.decision_id); aprovar marca o outcome.
    from edubot.agent.loop import run_agent
    from edubot.data.models.agent_decisions import AgentDecisions

    class _Brain:
        def __init__(self):
            self.i = 0

        def invoke(self, system, messages, tools, ctx):
            self.i += 1
            if self.i == 1:
                return {"model": "mock-model", "stop_reason": "tool_use", "usage": {},
                        "content": [{"type": "tool_use", "id": "t1",
                                     "name": "propor_mensagem_do_tutor",
                                     "input": {"mensagem_aluno": "Vamos conversar?"}}]}
            return {"model": "mock-model", "stop_reason": "end_turn", "usage": {},
                    "content": [{"type": "text", "text": "proposto"}]}

    result = run_agent("s", "u", T.schema_for(["propor_mensagem_do_tutor"]),
                       ctx={"student": Students.get_by_id(1)},
                       mock_client=_Brain(), trigger_type="sweep")
    alert = Alerts.get(Alerts.type == "mensagem_proposta")
    assert alert.decision_id == result["decision_id"]

    ap = client.post("/tutor/queue/approve",
                     data=json.dumps({"alert_id": alert.alert_id}), headers=auth(9))
    assert ap.status_code == 200
    assert AgentDecisions.get_by_id(result["decision_id"]).outcome == "aceita"


# --- fila de aprovação (rotas) ---------------------------------------------
def test_queue_approve_executes_once(client, auth, seeded_db):
    r = T.execute_tool("propor_mensagem_do_tutor",
                       {"mensagem_aluno": "Oi! Precisa de ajuda?"}, _ctx())
    alert_id = r["alert_id"]

    # tutor vê a fila
    q = client.get("/tutor/queue", headers=auth(9))
    assert q.status_code == 200
    assert len(json.loads(q.data)["fila"]) == 1

    # aprova -> cria a intervenção assinada "do tutor"
    ap = client.post("/tutor/queue/approve", data=json.dumps({"alert_id": alert_id}),
                     headers=auth(9))
    assert ap.status_code == 200
    assert Interventions.select().where(Interventions.type == "mensagem_tutor").count() == 1

    # idempotência: aprovar de novo não executa 2ª vez (item já tratado -> 404)
    ap2 = client.post("/tutor/queue/approve", data=json.dumps({"alert_id": alert_id}),
                      headers=auth(9))
    assert ap2.status_code == 404
    assert Interventions.select().where(Interventions.type == "mensagem_tutor").count() == 1


def test_queue_reject_no_effect_to_student(client, auth, seeded_db):
    r = T.execute_tool("propor_mensagem_do_tutor", {"mensagem_aluno": "..."}, _ctx())
    rej = client.post("/tutor/queue/reject", data=json.dumps({"alert_id": r["alert_id"]}),
                      headers=auth(9))
    assert rej.status_code == 200
    assert Interventions.select().count() == 0
    assert Alerts.get_by_id(r["alert_id"]).status == "rejeitado"


def test_queue_requires_staff(client, auth, seeded_db):
    assert client.get("/tutor/queue", headers=auth(1)).status_code == 403
