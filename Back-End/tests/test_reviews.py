"""D.3 — revisão espaçada (SM-2 simplificado)."""
import datetime

from edubot.data.models.review_schedule import ReviewSchedule
from edubot.services import reviews as R


def test_schedule_creates_and_is_idempotent(seeded_db):
    today = datetime.date(2026, 1, 1)
    r1 = R.schedule(1, 1, days_from_now=3, today=today)
    assert r1.due_date == today + datetime.timedelta(days=3)
    # reagendar não cria nova linha — reusa a ativa (idempotência)
    r2 = R.schedule(1, 1, days_from_now=5, today=today)
    assert ReviewSchedule.select().count() == 1
    assert r2.due_date == today + datetime.timedelta(days=5)


def test_correct_on_due_expands_interval(seeded_db):
    today = datetime.date(2026, 1, 1)
    ReviewSchedule.create(student_id=1, competency_id=1, due_date=today,
                          interval_days=3, ease=2.5, status="agendada")
    row = R.register_result(1, 1, True, today=today)
    # interval = round(3 * 2.5) = 8; due avança 8 dias
    assert row.interval_days == 8
    assert row.due_date == today + datetime.timedelta(days=8)


def test_wrong_on_due_resets(seeded_db):
    today = datetime.date(2026, 1, 1)
    ReviewSchedule.create(student_id=1, competency_id=1, due_date=today,
                          interval_days=8, ease=2.5, status="vencida")
    row = R.register_result(1, 1, False, today=today)
    assert row.interval_days == 1
    assert abs(row.ease - 2.3) < 1e-9
    assert row.due_date == today + datetime.timedelta(days=1)


def test_result_before_due_does_nothing(seeded_db):
    today = datetime.date(2026, 1, 1)
    future = today + datetime.timedelta(days=5)
    ReviewSchedule.create(student_id=1, competency_id=1, due_date=future,
                          interval_days=5, ease=2.5, status="agendada")
    assert R.register_result(1, 1, True, today=today) is None


def test_on_attempt_autoschedules_when_mastered(seeded_db):
    today = datetime.date(2026, 1, 1)
    # domínio >= 0.8 e sem revisão ativa -> agenda a 1ª revisão
    R.on_attempt(1, 1, True, p_mastery=0.85, today=today)
    row = R._active(1, 1)
    assert row is not None
    assert row.created_by == "rule"
    assert row.due_date == today + datetime.timedelta(days=R.REVIEW_FIRST_DAYS)


def test_on_attempt_no_schedule_below_threshold(seeded_db):
    R.on_attempt(1, 1, False, p_mastery=0.3, today=datetime.date(2026, 1, 1))
    assert R._active(1, 1) is None


def test_mark_due_and_due_reviews(seeded_db):
    today = datetime.date(2026, 1, 10)
    ReviewSchedule.create(student_id=1, competency_id=1,
                          due_date=today - datetime.timedelta(days=1),
                          interval_days=3, ease=2.5, status="agendada")
    assert R.mark_due_reviews(today) == 1
    row = R._active(1, 1)
    assert row.status == "vencida"
    assert len(R.due_reviews(1, today=today)) == 1


def test_get_reviews_route(client, auth, seeded_db):
    import json
    today = datetime.date.today()
    ReviewSchedule.create(student_id=1, competency_id=1, due_date=today,
                          interval_days=1, ease=2.5, status="vencida")
    resp = client.get("/reviews", headers=auth())
    assert resp.status_code == 200
    data = json.loads(resp.data)["reviews"]
    assert len(data) == 1 and data[0]["vencida"] is True
