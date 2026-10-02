"""U.1 — o quiz do módulo só libera após consumir o conteúdo (gate no backend)."""
import json

from edubot.data.models.ovas import OVAs
from edubot.data.models.questions import Questions
from edubot.data.models.ova_progress import OVAProgress


def _gated_ova(gate=70):
    """OVA com gate + uma questão (subject 1 do seed)."""
    ova = OVAs.create(ova_id=50, ova_name="Gated", subject_id=1,
                      num_interactions=0, link="g.html", quiz_gate_perc=gate)
    Questions.create(question_id=50, statement="q", answer="a",
                     alternatives={"alternatives": ["x", "y"]},
                     ova_id=50, competency_id=1)
    return ova


def test_quiz_locked_without_reading(client, auth, seeded_db):
    _gated_ova(gate=70)
    r = client.post("/question/ova", headers=auth(1), data=json.dumps({"ova_id": 50}))
    assert r.status_code == 403
    body = json.loads(r.data.decode())
    assert body["error"] == "quiz_locked" and body["gate"] == 70 and body["perc"] == 0


def test_quiz_unlocks_after_reading(client, auth, seeded_db):
    _gated_ova(gate=70)
    OVAProgress.create(student_id=1, ova_id=50, read_time=100, perc_scrolled=90,
                       completed=False)
    r = client.post("/question/ova", headers=auth(1), data=json.dumps({"ova_id": 50}))
    assert r.status_code == 200
    assert isinstance(json.loads(r.data.decode()), list)


def test_gate_zero_always_open(client, auth, seeded_db):
    _gated_ova(gate=0)
    r = client.post("/question/ova", headers=auth(1), data=json.dumps({"ova_id": 50}))
    assert r.status_code == 200


def test_answer_blocked_when_quiz_locked(client, auth, seeded_db):
    # Defesa em profundidade: /answer também recusa se o quiz está travado.
    _gated_ova(gate=70)
    r = client.post("/question/answer", headers=auth(1),
                    data=json.dumps({"question_id": 50, "selected": "a"}))
    assert r.status_code == 403
    assert json.loads(r.data.decode())["error"] == "quiz_locked"


def test_answer_allowed_after_reading(client, auth, seeded_db):
    _gated_ova(gate=70)
    OVAProgress.create(student_id=1, ova_id=50, read_time=100, perc_scrolled=75,
                       completed=False)
    r = client.post("/question/answer", headers=auth(1),
                    data=json.dumps({"question_id": 50, "selected": "a"}))
    assert r.status_code == 200
    assert json.loads(r.data.decode())["is_correct"] is True
