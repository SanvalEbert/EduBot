"""B.3 — loop de tool-use genérico + catálogo/tools novas."""
import datetime

from edubot.agent.loop import run_agent
from edubot.agent import tools as T
from edubot.data.models.agent_decisions import AgentDecisions
from edubot.data.models.interventions import Interventions
from edubot.data.models.review_schedule import ReviewSchedule
from edubot.data.models.students import Students


class _ScriptedBrain:
    """Cérebro determinístico para o teste: emite uma sequência fixa de envelopes
    (mesmo formato da Messages API) contando as chamadas."""
    def __init__(self, steps):
        self.steps = steps
        self.i = 0

    def invoke(self, system, messages, tools, ctx):
        step = self.steps[min(self.i, len(self.steps) - 1)]
        self.i += 1
        return step


def _tool_use(name, inp):
    return {"model": "mock-model", "stop_reason": "tool_use", "usage": {},
            "content": [{"type": "tool_use", "id": f"toolu_{name}", "name": name, "input": inp}]}


def _text(t):
    return {"model": "mock-model", "stop_reason": "end_turn", "usage": {},
            "content": [{"type": "text", "text": t}]}


def test_run_agent_executes_tools_and_records(seeded_db):
    student = Students.get_by_id(1)
    brain = _ScriptedBrain([
        _tool_use("obter_perfil_resumido", {}),
        _tool_use("criar_intervencao", {"tipo": "plano_retomada",
                                        "mensagem_aluno": "Oi Ana, bora retomar!"}),
        _text("Pronto, falei com a aluna."),
    ])
    result = run_agent(
        "system", "user", T.schema_for(["obter_perfil_resumido", "criar_intervencao"]),
        ctx={"student": student}, mock_client=brain, trigger_type="on_demand")

    assert result["mock"] is True
    assert result["final_text"].startswith("Pronto")
    names = [t["name"] for t in result["tools_called"]]
    assert names == ["obter_perfil_resumido", "criar_intervencao"]
    # a intervenção foi criada e a decisão registrada (B.2)
    assert Interventions.select().where(Interventions.student_id == 1).count() == 1
    assert AgentDecisions.select().where(
        AgentDecisions.trigger_type == "on_demand").count() == 1


def test_run_agent_requires_brain_when_mock(seeded_db):
    import pytest
    with pytest.raises(RuntimeError):
        run_agent("s", "u", [], ctx={"student": Students.get_by_id(1)}, mock_client=None)


def test_run_agent_falls_back_to_mock_when_real_fails(seeded_db, monkeypatch):
    # Etapa 7 (auditoria de smoke): LLM real falha no loop (token expirado) e há
    # mock -> degrada em vez de estourar 500. A decisão fica registrada como mock.
    from edubot.agent import loop as L

    monkeypatch.setattr(L.llm, "is_real", lambda: True)

    class _Boom:
        def __init__(self, *a, **k):
            pass

        def invoke(self, **k):
            raise RuntimeError("Bearer Token has expired")

    monkeypatch.setattr(L, "_RealAgentClient", _Boom)
    brain = _ScriptedBrain([_text("caí no mock, tudo bem")])
    result = run_agent("s", "u", [], ctx={"student": Students.get_by_id(1)},
                       mock_client=brain, trigger_type="on_demand")
    assert result["mock"] is True
    assert result["final_text"] == "caí no mock, tudo bem"
    assert result["estimated_cost_usd"] == 0.0


def test_criar_intervencao_is_idempotent(seeded_db):
    student = Students.get_by_id(1)
    ctx = {"student": student}
    r1 = T.execute_tool("criar_intervencao",
                        {"tipo": "trilha_minima", "mensagem_aluno": "foco"}, ctx)
    r2 = T.execute_tool("criar_intervencao",
                        {"tipo": "trilha_minima", "mensagem_aluno": "foco de novo"}, ctx)
    assert "intervention_id" in r1
    assert r2.get("dedup") is True
    assert Interventions.select().count() == 1


def test_agendar_revisao_validates_ownership(seeded_db):
    student = Students.get_by_id(1)
    ctx = {"student": student}
    # competência 1 é do curso do aluno -> ok
    ok = T.execute_tool("agendar_revisao", {"competency_id": 1, "days_from_now": 4}, ctx)
    assert "review_id" in ok
    assert ReviewSchedule.select().count() == 1
    # competência inexistente -> erro (não persiste)
    bad = T.execute_tool("agendar_revisao", {"competency_id": 999}, ctx)
    assert "error" in bad
    assert ReviewSchedule.select().count() == 1


def test_tier_metadata():
    assert T.tier_of("listar_competencias_fracas") == "read"
    assert T.tier_of("criar_intervencao") == "auto"
    assert T.tier_of("agendar_revisao") == "auto"
    assert T.tier_of("desconhecida") == "read"


def test_schema_for_subset():
    schemas = T.schema_for(["obter_perfil_resumido", "criar_intervencao", "inexistente"])
    names = {s["name"] for s in schemas}
    assert names == {"obter_perfil_resumido", "criar_intervencao"}
