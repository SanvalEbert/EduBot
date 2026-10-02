"""D.2 — mastery por competência (BKT + decaimento + backfill)."""
import datetime

import pytest

from edubot.data.models.attempts import Attempts
from edubot.data.models.student_mastery import StudentMastery
from edubot.services import mastery as M


def test_bkt_single_correct(seeded_db):
    # p_init=0.20, correto: p_given=0.18/0.38=0.47368; +learn -> 0.55263
    p = M.update_on_attempt(1, 1, True)
    assert p == pytest.approx(0.55263, abs=1e-4)
    row = StudentMastery.get((StudentMastery.student_id == 1) &
                             (StudentMastery.competency_id == 1))
    assert row.attempts_seen == 1


def test_bkt_single_wrong(seeded_db):
    # p_init=0.20, errado: p_given=0.02/0.62=0.032258; +learn -> 0.17742
    p = M.update_on_attempt(1, 1, False)
    assert p == pytest.approx(0.17742, abs=1e-4)


def test_bkt_correct_increases_wrong_decreases(seeded_db):
    # Uma sequência de acertos sobe monotonicamente; um erro no fim derruba.
    p1 = M.update_on_attempt(1, 1, True)
    p2 = M.update_on_attempt(1, 1, True)
    p3 = M.update_on_attempt(1, 1, True)
    assert p1 < p2 < p3
    p4 = M.update_on_attempt(1, 1, False)
    assert p4 < p3


def test_decay_reduces_mastery_over_time():
    t0 = datetime.datetime(2024, 1, 1, 12, 0, 0)
    # 4 semanas: decay=min(1, 4*0.02)=0.08; 0.80 -> 0.80-(0.80-0.20)*0.08=0.752
    decayed = M._apply_decay(0.80, t0, t0 + datetime.timedelta(weeks=4))
    assert decayed == pytest.approx(0.752, abs=1e-3)
    assert decayed < 0.80


def test_decay_never_below_init():
    t0 = datetime.datetime(2024, 1, 1)
    # decaimento muito longo satura em P_INIT, não abaixo
    decayed = M._apply_decay(0.90, t0, t0 + datetime.timedelta(weeks=500))
    assert decayed == pytest.approx(M.P_INIT, abs=1e-6)


def test_status_from_mastery():
    assert M.status_from_mastery(0.85) == "desenvolvida"
    assert M.status_from_mastery(0.5) == "em desenvolvimento"
    assert M.status_from_mastery(0.2) == "não iniciada"
    assert M.status_from_mastery(None) is None


def test_backfill_idempotent(seeded_db):
    from tools.backfill_mastery import run
    now = datetime.datetime.now()
    Attempts.create(student_id=1, question_id=1, is_correct=True, attempt_time=now)
    Attempts.create(student_id=1, question_id=1, is_correct=False,
                    attempt_time=now + datetime.timedelta(minutes=1))
    Attempts.create(student_id=1, question_id=2, is_correct=True,
                    attempt_time=now + datetime.timedelta(minutes=2))

    run()
    first = {(m.student_id.student_id, m.competency_id.competency_id): m.p_mastery
             for m in StudentMastery.select()}
    run()  # segunda passada
    second = {(m.student_id.student_id, m.competency_id.competency_id): m.p_mastery
              for m in StudentMastery.select()}
    assert first == second
    # q1 e q2 são da competência 1 -> um par (1,1); attempts_seen == 3
    row = StudentMastery.get((StudentMastery.student_id == 1) &
                             (StudentMastery.competency_id == 1))
    assert row.attempts_seen == 3


def test_profile_exposes_dominio_estimado(seeded_db):
    from edubot.services.student_context import build_student_profile
    from edubot.data.models.students import Students
    M.update_on_attempt(1, 1, True)
    profile = build_student_profile(Students.get_by_id(1))
    comp = [c for c in profile["competencias"] if c["competency_id"] == 1][0]
    assert comp["dominio_estimado"] == pytest.approx(0.55, abs=0.02)
    assert comp["status"] == "em desenvolvimento"
