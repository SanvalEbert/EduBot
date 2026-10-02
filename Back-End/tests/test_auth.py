"""A3 — autenticação e aluno resolvido pelo token (anti-IDOR)."""
import json

from edubot.data.models.interactions import Interactions


def test_interaction_requires_auth(client):
    r = client.post("/interaction/register",
                    data=json.dumps({"ova_id": 1, "action": "ova_opened"}),
                    content_type="application/json")
    assert r.status_code == 401


def test_interaction_attributed_to_token_not_payload(client, auth):
    # payload tenta forjar student_id=2, mas o token é do aluno 1
    r = client.post("/interaction/register", headers=auth(1),
                    data=json.dumps({"ova_id": 1, "action": "ova_opened", "student_id": 2}))
    assert r.status_code == 200
    assert Interactions.select().where(Interactions.student_id == 2).count() == 0
    assert Interactions.select().where(Interactions.student_id == 1).count() == 1


def test_ova_questions_requires_auth(client):
    r = client.post("/question/ova", data=json.dumps({"ova_id": 1}),
                    content_type="application/json")
    assert r.status_code == 401


def test_report_route_is_retired(client, auth):
    # /student/report foi aposentada (substituída por student_context) -> 404
    r = client.get("/student/report/1", headers=auth(1))
    assert r.status_code == 404
