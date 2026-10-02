"""Etapa 11 (Plano 3) — persona no cérebro do tutor + flag do companheiro."""
import json

from edubot.agent import persona as P
from edubot.agent.tutor import tutor_reply

_CTX = "## Introdução\nO conteúdo fala sobre derivadas e limites.\n"
_ASK = [{"role": "user", "content": "o que é uma derivada?"}]


# --- CP.4: estilo/bordão por persona --------------------------------------
def test_normalize_persona():
    assert P.normalize_persona("einstein") == "einstein"
    assert P.normalize_persona("CURIE") == "curie"
    assert P.normalize_persona("edubot") is None      # mascote = tom neutro
    assert P.normalize_persona("batman") is None
    assert P.normalize_persona(None) is None


def test_style_prompt_only_for_scientists():
    assert "Einstein" in P.style_prompt("einstein", "pt")
    assert "Curie" in P.style_prompt("curie", "en")
    assert P.style_prompt("edubot", "pt") == ""
    assert P.style_prompt("xpto", "pt") == ""


def test_tutor_reply_prepends_persona_bordao():
    r = tutor_reply("Cálculo", _CTX, _ASK, lang="pt", persona="einstein")
    assert r["reply"].startswith(tuple(P._BORDAO["einstein"]["pt"]))
    c = tutor_reply("Cálculo", _CTX, _ASK, lang="pt", persona="curie")
    assert c["reply"].startswith(tuple(P._BORDAO["curie"]["pt"]))


def test_tutor_reply_neutral_without_persona():
    r = tutor_reply("Cálculo", _CTX, _ASK, lang="pt")
    todos = P._BORDAO["einstein"]["pt"] + P._BORDAO["curie"]["pt"]
    assert not r["reply"].startswith(tuple(todos))   # sem bordão de persona
    # persona inválida também cai no neutro (não quebra)
    r2 = tutor_reply("Cálculo", _CTX, _ASK, lang="pt", persona="batman")
    assert not r2["reply"].startswith(tuple(todos))


def test_tutor_chat_route_threads_persona(client, auth, seeded_db):
    body = {"ova_id": 1, "context": _CTX, "messages": _ASK, "persona": "einstein"}
    resp = client.post("/edubot/tutor-chat", data=json.dumps(body), headers=auth(1))
    assert resp.status_code == 200
    reply = json.loads(resp.data)["reply"]
    assert reply.startswith(tuple(P._BORDAO["einstein"]["pt"]))


# --- CP.1: flag do companheiro em /student/me ------------------------------
def test_features_companion_default_on(client, auth, seeded_db):
    me = json.loads(client.get("/student/me", headers=auth(1)).data)
    assert me["features"]["companion"] is True


def test_features_companion_off(client, auth, seeded_db, monkeypatch):
    monkeypatch.setenv("EDUBOT_COMPANION", "off")
    me = json.loads(client.get("/student/me", headers=auth(1)).data)
    assert me["features"]["companion"] is False
