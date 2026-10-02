"""A13 (base) — motor de regras determinístico do EduBot.

As regras são o gatilho barato da proatividade; a redação pela LLM vem depois.
Aqui garantimos que a avaliação determinística escolhe a regra certa.
"""
from edubot.agent import get_recommendation
from edubot.agent.prompt import RULES


def _base_profile(**over):
    prof = {
        "estudante": {"nome": "Ana Souza", "student_id": 1},
        "dias_sem_acesso": 0,
        "recursos": {"percentual_consumido": 100},
        "quiz": {"taxa_erro": 0.0},
        "atividades_pendentes": 0,
        "preferencia_formato": "video",
        "competencias": [],
    }
    prof.update(over)
    return prof


def test_recommendation_has_contract_keys():
    rec = get_recommendation(_base_profile())
    for key in ("tipo", "prioridade", "titulo", "mensagem_aluno", "acoes", "justificativa"):
        assert key in rec


def test_rule1_inactivity_fires_for_long_absence():
    dias = RULES["INACTIVITY_DAYS"] + 5
    rec = get_recommendation(_base_profile(dias_sem_acesso=dias))
    assert rec["tipo"] == "plano_retomada"
    assert rec["prioridade"] == "alta"


def test_low_consumption_triggers_minimum_track():
    rec = get_recommendation(_base_profile(
        recursos={"percentual_consumido": 0}))
    # com inatividade 0 e consumo 0, a Regra 2 (trilha mínima) deve disparar
    assert rec["tipo"] == "trilha_minima"
