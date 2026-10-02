"""H.1 (Plano 2) — snapshot diário do domínio + tendência de 7 dias."""
import datetime
import json

from edubot.data.models.student_mastery import StudentMastery
from edubot.data.models.student_mastery_history import StudentMasteryHistory
from edubot.services import mastery as M


def _mastery(sid, cid, p):
    StudentMastery.create(student_id=sid, competency_id=cid, p_mastery=p,
                          attempts_seen=1, updated_at=datetime.datetime.now())


def test_snapshot_is_idempotent_per_day(seeded_db):
    _mastery(1, 1, 0.3)
    today = datetime.date(2026, 7, 10)
    assert M.snapshot_today(today) == 1
    # rodar de novo no MESMO dia não duplica; atualiza o valor
    StudentMastery.update(p_mastery=0.5).where(StudentMastery.student_id == 1).execute()
    assert M.snapshot_today(today) == 0
    assert StudentMasteryHistory.select().count() == 1
    row = StudentMasteryHistory.get()
    assert abs(row.p_mastery - 0.5) < 1e-6


def test_trend_delta_over_window(seeded_db):
    _mastery(1, 1, 0.6)   # domínio atual
    today = datetime.date(2026, 7, 10)
    # baseline 5 dias atrás: 0.4
    StudentMasteryHistory.create(student_id=1, competency_id=1,
                                 snapshot_date=today - datetime.timedelta(days=5),
                                 p_mastery=0.4)
    trend = M.mastery_trend(1, days=7, today=today)
    assert trend[1]["anterior"] == 0.4
    assert trend[1]["atual"] == 0.6
    assert trend[1]["delta"] == 0.2
    assert trend[1]["direcao"] == "up"


def test_trend_ignores_baseline_outside_window(seeded_db):
    _mastery(1, 1, 0.6)
    today = datetime.date(2026, 7, 10)
    # snapshot 20 dias atrás está FORA da janela de 7 -> sem baseline -> sem tendência
    StudentMasteryHistory.create(student_id=1, competency_id=1,
                                 snapshot_date=today - datetime.timedelta(days=20),
                                 p_mastery=0.1)
    assert M.mastery_trend(1, days=7, today=today) == {}


def test_trend_route(client, auth, seeded_db):
    _mastery(1, 1, 0.7)
    StudentMasteryHistory.create(student_id=1, competency_id=1,
                                 snapshot_date=datetime.date.today() - datetime.timedelta(days=3),
                                 p_mastery=0.5)
    resp = client.get("/mastery/trend", headers=auth(1))
    assert resp.status_code == 200
    trend = json.loads(resp.data)["trend"]
    assert trend[0]["competency_id"] == 1
    assert trend[0]["direcao"] == "up"
