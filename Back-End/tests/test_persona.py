"""AV.2 (Plano 3) — persona do companheiro persistida no servidor."""
import json

from edubot.data.models.students import Students


def test_default_persona_is_edubot(client, auth, seeded_db):
    body = json.loads(client.get("/student/me", headers=auth(1)).data)
    assert body["estudante"]["persona"] == "edubot"


def test_set_persona_persists_and_reflects_in_profile(client, auth, seeded_db):
    resp = client.post("/student/persona",
                       data=json.dumps({"persona": "einstein"}), headers=auth(1))
    assert resp.status_code == 200
    assert json.loads(resp.data)["persona"] == "einstein"
    # gravou no banco...
    assert Students.get_by_id(1).persona == "einstein"
    # ...e o perfil já reflete
    me = json.loads(client.get("/student/me", headers=auth(1)).data)
    assert me["estudante"]["persona"] == "einstein"


def test_set_persona_is_case_insensitive(client, auth, seeded_db):
    resp = client.post("/student/persona",
                       data=json.dumps({"persona": "Curie"}), headers=auth(1))
    assert resp.status_code == 200
    assert Students.get_by_id(1).persona == "curie"


def test_set_invalid_persona_rejected(client, auth, seeded_db):
    resp = client.post("/student/persona",
                       data=json.dumps({"persona": "batman"}), headers=auth(1))
    assert resp.status_code == 400
    # não altera a persona atual
    assert Students.get_by_id(1).persona == "edubot"


def test_set_persona_requires_auth(client, seeded_db):
    resp = client.post("/student/persona",
                       data=json.dumps({"persona": "einstein"}),
                       headers={"Content-Type": "application/json"})
    assert resp.status_code == 401
