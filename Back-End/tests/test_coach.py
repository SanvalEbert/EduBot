"""Fase 3d — coach unificado no provider llm.py, degradável."""
from edubot.agent import llm
from edubot.agent.coach import coach_message


def test_coach_returns_none_in_mock_mode():
    # Sem provider real (mock, padrão dos testes) o coach devolve None e o
    # frontend usa o texto determinístico local — nenhuma chamada de rede.
    assert llm.is_real() is False
    assert coach_message({"estudante": {"nome": "Ana"}, "recursos": {},
                          "quiz": {}, "competencias": []}) is None


def test_model_id_override_and_bedrock_prefix(monkeypatch):
    # override plano ganha prefixo anthropic. na Bedrock; inference profile
    # (us.anthropic.) é preservado.
    monkeypatch.setattr(llm, "PROVIDER", "bedrock")
    assert llm.model_id("claude-haiku-4-5-20251001") == "anthropic.claude-haiku-4-5-20251001"
    assert llm.model_id("us.anthropic.foo-v1:0") == "us.anthropic.foo-v1:0"
