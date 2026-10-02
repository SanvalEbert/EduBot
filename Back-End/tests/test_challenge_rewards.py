"""R.1/R.2/R.3 (Plano 2) — desafios avançados, personas por nível, títulos."""
import datetime
import json

import pytest

from edubot.data.models.questions import Questions
from edubot.data.models.student_achievements import StudentAchievements
from edubot.data.models.student_mastery import StudentMastery
from edubot.data.models.students import Students
from edubot.services import gamification as G


@pytest.fixture(autouse=True)
def _gami_on(monkeypatch):
    monkeypatch.setenv("EDUBOT_GAMIFICATION", "on")
    yield


def _master(sid=1, cid=1, p=0.85):
    StudentMastery.create(student_id=sid, competency_id=cid, p_mastery=p,
                          attempts_seen=5, updated_at=datetime.datetime.now())


def _hard_question(qid=3, cid=1):
    Questions.create(question_id=qid, statement="desafio",
                     alternatives={"alternatives": ["a", "b"]}, answer="a",
                     ova_id=1, competency_id=cid, difficulty=3)


# --- R.3 modo desafio ------------------------------------------------------
def test_challenge_locked_without_mastery(client, auth, seeded_db):
    _hard_question()
    # sem domínio -> challenge_locked 403
    resp = client.post("/question/ova", data=json.dumps({"ova_id": 1, "desafio": True}),
                       headers=auth(1))
    assert resp.status_code == 403
    assert json.loads(resp.data)["error"] == "challenge_locked"


def test_challenge_serves_only_hard_of_mastered(client, auth, seeded_db):
    _master()
    _hard_question(qid=3)
    resp = client.post("/question/ova", data=json.dumps({"ova_id": 1, "desafio": True}),
                       headers=auth(1))
    assert resp.status_code == 200
    qs = json.loads(resp.data)
    assert [q["question_id"] for q in qs] == [3]     # só a difícil da competência dominada
    assert all(q["difficulty"] == 3 for q in qs)


def test_answering_hard_mastered_awards_challenge_xp(client, auth, seeded_db):
    _master()
    _hard_question(qid=3)
    resp = client.post("/question/answer",
                       data=json.dumps({"question_id": 3, "selected": "a"}), headers=auth(1))
    gami = json.loads(resp.data)["gamification"]
    # desafio_tentado (20) entra no XP e a conquista `desafiante` é desbloqueada
    assert gami["xp_awarded"] >= 20
    assert StudentAchievements.select().where(
        (StudentAchievements.student_id == 1) &
        (StudentAchievements.achievement_id == "desafiante")).exists()


# --- AV.1 (Plano 3): personas LIVRES (a trava R.1 por nível foi REVOGADA) ---
def test_personas_always_unlocked(seeded_db):
    # personas são ferramenta de estudo, não recompensa: livres em qualquer nível.
    for level in (1, 4, 9):
        assert G.personas_state(level) == [
            {"id": "einstein", "unlock_level": 0, "unlocked": True},
            {"id": "curie", "unlock_level": 0, "unlocked": True},
        ]
    # sem argumento também (assinatura de compat)
    assert all(p["unlocked"] for p in G.personas_state())


# --- R.2 títulos -----------------------------------------------------------
def test_titles_from_achievements_and_set(client, auth, seeded_db):
    StudentAchievements.create(student_id=1, achievement_id="revisor_pontual",
                               unlocked_at=datetime.datetime.now())
    titles = G.available_titles(1)
    assert any(t["id"] == "revisor_pontual" for t in titles)
    # define o título ganho
    resp = client.post("/gamification/title",
                       data=json.dumps({"title_id": "revisor_pontual"}), headers=auth(1))
    assert resp.status_code == 200
    assert Students.get_by_id(1).title == "Revisor Pontual"


def test_set_title_rejects_unearned(client, auth, seeded_db):
    resp = client.post("/gamification/title",
                       data=json.dumps({"title_id": "mestre_competencia"}), headers=auth(1))
    assert resp.status_code == 400


def test_title_translated_and_id_exposed(client, auth, seeded_db):
    # AUDITORIA P2 (F3): o rótulo gravado é PT, mas /gamification/me devolve
    # title_id + rótulo TRADUZIDO — a UI em EN casa o select e traduz a exibição.
    StudentAchievements.create(student_id=1, achievement_id="revisor_pontual",
                               unlocked_at=datetime.datetime.now())
    client.post("/gamification/title",
                data=json.dumps({"title_id": "revisor_pontual"}), headers=auth(1))
    pt = json.loads(client.get("/gamification/me?lang=pt", headers=auth(1)).data)
    en = json.loads(client.get("/gamification/me?lang=en", headers=auth(1)).data)
    assert pt["title_id"] == en["title_id"] == "revisor_pontual"
    assert pt["title"] == "Revisor Pontual"
    assert en["title"] == "On-time Reviewer"
