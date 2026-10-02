"""D.6 — heatmap de mastery do tutor."""
import datetime
import json

from edubot.data.models.student_mastery import StudentMastery


def _mastery(sid, cid, p):
    StudentMastery.create(student_id=sid, competency_id=cid, p_mastery=p,
                          attempts_seen=1, updated_at=datetime.datetime.now())


def test_tutor_mastery_heatmap(client, auth, seeded_db):
    # aluno 1 domina comp1, aluno 2 é frágil
    _mastery(1, 1, 0.9)
    _mastery(2, 1, 0.2)
    resp = client.get("/tutor/mastery", headers=auth(9))  # student 9 = tutor
    assert resp.status_code == 200
    data = json.loads(resp.data)

    comp1 = [c for c in data["competencias"] if c["competency_id"] == 1][0]
    assert comp1["n"] == 2
    assert abs(comp1["media"] - 0.55) < 1e-6
    assert comp1["distribuicao"]["desenvolvida"] == 1
    assert comp1["distribuicao"]["fragil"] == 1

    # matriz: 2 alunos, célula com p_mastery e status
    assert len(data["matriz"]) == 2
    nomes = {row["nome"] for row in data["matriz"]}
    assert "Ana Souza" in nomes


def test_tutor_mastery_requires_staff(client, auth, seeded_db):
    resp = client.get("/tutor/mastery", headers=auth(1))  # aluno comum
    assert resp.status_code == 403
