"""D.4 — dificuldade por questão + pool adaptativo (zona proximal)."""
import json

from edubot.data.models.questions import Questions
from edubot.data.models.student_mastery import StudentMastery
from edubot.services import quiz as Q
from edubot.services import mastery as M


def test_difficulty_ceiling():
    assert Q.difficulty_ceiling(None) == 2      # sem sinal -> até média
    assert Q.difficulty_ceiling(0.3) == 2       # iniciante
    assert Q.difficulty_ceiling(0.79) == 2      # intermediário
    assert Q.difficulty_ceiling(0.8) == 3       # domina -> difíceis liberadas


def test_adaptive_pool_excludes_hard_when_low(seeded_db):
    # seed: q1,q2 (difficulty 2, comp 1). Adiciona uma difícil (3).
    Questions.create(question_id=3, statement="dificil",
                     alternatives={"alternatives": ["a", "b"]}, answer="a",
                     ova_id=1, competency_id=1, difficulty=3)
    qs = list(Questions.select().where(Questions.ova_id == 1))
    # sem mastery (None) -> teto 2 -> exclui a difícil
    pool = Q.adaptive_pool(qs, {})
    ids = [q.question_id for q in pool]
    assert 3 not in ids
    # domínio alto -> inclui a difícil, e ela vem por último (ordem asc)
    pool_hi = Q.adaptive_pool(qs, {1: 0.9})
    assert pool_hi[-1].question_id == 3


def test_adaptive_pool_orders_easy_first(seeded_db):
    Questions.create(question_id=3, statement="facil",
                     alternatives={"alternatives": ["a", "b"]}, answer="a",
                     ova_id=1, competency_id=1, difficulty=1)
    qs = list(Questions.select().where(Questions.ova_id == 1))
    pool = Q.adaptive_pool(qs, {})
    assert [q.difficulty for q in pool] == sorted(q.difficulty for q in pool)
    assert pool[0].question_id == 3  # a fácil primeiro


def test_adaptive_pool_never_empty(seeded_db):
    # Só há difícil e o aluno não domina -> não devolve quiz vazio (degradação).
    Questions.delete().where(Questions.ova_id == 1).execute()
    Questions.create(question_id=9, statement="so dificil",
                     alternatives={"alternatives": ["a", "b"]}, answer="a",
                     ova_id=1, competency_id=1, difficulty=3)
    qs = list(Questions.select().where(Questions.ova_id == 1))
    pool = Q.adaptive_pool(qs, {})
    assert len(pool) == 1


def test_question_ova_serves_adaptive_pool(client, auth, seeded_db):
    # OVA1 do seed tem gate 0 (desbloqueado). Adiciona uma questão difícil.
    Questions.create(question_id=3, statement="dificil",
                     alternatives={"alternatives": ["a", "b"]}, answer="a",
                     ova_id=1, competency_id=1, difficulty=3)
    # aluno sem mastery -> difícil não aparece
    resp = client.post("/question/ova", data=json.dumps({"ova_id": 1}), headers=auth())
    ids = [q["question_id"] for q in json.loads(resp.data)]
    assert 3 not in ids

    # domina a competência 1 -> difícil aparece
    M.update_on_attempt(1, 1, True)
    StudentMastery.update(p_mastery=0.9).where(
        (StudentMastery.student_id == 1) & (StudentMastery.competency_id == 1)).execute()
    resp2 = client.post("/question/ova", data=json.dumps({"ova_id": 1}), headers=auth())
    ids2 = [q["question_id"] for q in json.loads(resp2.data)]
    assert 3 in ids2


def test_calibration_from_history(seeded_db):
    from edubot.data.models.attempts import Attempts
    from tools.calibrate_difficulty import run
    # q1: 3 erros / 4 -> 75% > 60% -> difícil (3)
    Attempts.create(student_id=1, question_id=1, is_correct=True)
    for _ in range(3):
        Attempts.create(student_id=1, question_id=1, is_correct=False)
    # q2: 0 erro / 3 -> 0% < 25% -> fácil (1)
    for _ in range(3):
        Attempts.create(student_id=1, question_id=2, is_correct=True)
    run()
    assert Questions.get_by_id(1).difficulty == 3
    assert Questions.get_by_id(2).difficulty == 1
