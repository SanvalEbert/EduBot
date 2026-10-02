"""A7 — correção server-side e tentativas idempotentes."""
import json

from edubot.data.models.attempts import Attempts
from edubot.data.models.answers import Answers


def _answer(client, headers, qid, selected):
    return client.post("/question/answer", headers=headers,
                       data=json.dumps({"question_id": qid, "selected": selected}))


def test_grading_is_server_side(client, auth):
    h = auth(1)
    r_ok = _answer(client, h, 1, "b")   # gabarito é "b"
    r_no = _answer(client, h, 2, "b")   # gabarito da q2 é "a"
    assert json.loads(r_ok.data.decode())["is_correct"] is True
    assert json.loads(r_no.data.decode())["is_correct"] is False


def test_repeat_correct_answer_does_not_duplicate_attempt(client, auth):
    h = auth(1)
    _answer(client, h, 1, "b")
    _answer(client, h, 1, "b")  # reenvio da mesma resposta correta
    _answer(client, h, 1, "b")
    n = Attempts.select().where(Attempts.student_id == 1, Attempts.question_id == 1).count()
    assert n == 1
    assert Answers.select().where(Answers.student_id == 1, Answers.question_id == 1).count() == 1


def test_wrong_then_correct_counts_two_attempts(client, auth):
    h = auth(1)
    _answer(client, h, 1, "a")  # errada
    _answer(client, h, 1, "b")  # correta (retentativa legítima)
    n = Attempts.select().where(Attempts.student_id == 1, Attempts.question_id == 1).count()
    assert n == 2


def test_answer_requires_auth(client):
    r = client.post("/question/answer", data=json.dumps({"question_id": 1, "selected": "b"}),
                    content_type="application/json")
    assert r.status_code == 401
