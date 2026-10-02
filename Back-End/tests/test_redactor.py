"""B.4 — redator de intervenção por caso (Haiku) + fallback template."""
from types import SimpleNamespace

from edubot.agent import llm
from edubot.agent import redactor


REC = {"tipo": "trilha_minima", "prioridade": "alta",
       "mensagem_aluno": "Template padrão: foque nos essenciais."}
DIGEST = {"primeiro_nome": "Ana", "competencia_mais_fraca": "Álgebra",
          "ultimas_perguntas_tutor": ["o que é uma matriz?"]}


def test_redactor_returns_none_in_mock_mode(monkeypatch):
    # provider mock -> is_real False -> sem redação (o chamador usa o template)
    monkeypatch.setattr(llm, "PROVIDER", "mock")
    llm.reset_breaker()
    assert redactor.redigir_intervencao(DIGEST, REC, "pt") is None


def test_redactor_uses_llm_when_real(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    llm.reset_breaker()

    captured = {}

    def fake_create(system, messages, max_tokens=None, model=None, tools=None):
        captured["model"] = model
        captured["system"] = system
        return SimpleNamespace(content=[SimpleNamespace(type="text",
                               text="Oi Ana! Vi que você perguntou sobre matrizes...")])

    monkeypatch.setattr(llm, "messages_create", fake_create)
    text = redactor.redigir_intervencao(DIGEST, REC, "pt")
    assert text.startswith("Oi Ana")
    # usa o modelo barato do redator e o system é cacheável (lista de blocos)
    assert "haiku" in (captured["model"] or "").lower()
    assert isinstance(captured["system"], list)
    assert captured["system"][0]["cache_control"]["type"] == "ephemeral"


def test_redactor_falls_back_on_error(monkeypatch):
    monkeypatch.setattr(llm, "PROVIDER", "anthropic")
    llm.reset_breaker()

    def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm, "messages_create", boom)
    assert redactor.redigir_intervencao(DIGEST, REC, "pt") is None
