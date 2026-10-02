"""E.3 (Plano 2) — metas semanais."""
import datetime
import json

import pytest

from edubot.data.models.review_schedule import ReviewSchedule
from edubot.data.models.weekly_goals import WeeklyGoals
from edubot.services import goals as GO
from edubot.services import gamification as G


@pytest.fixture(autouse=True)
def _gami_on(monkeypatch):
    monkeypatch.setenv("EDUBOT_GAMIFICATION", "on")
    yield


def _week():
    return G._week_start(datetime.date(2026, 7, 6))   # segunda-feira


def test_suggest_creates_two_goals_idempotent(seeded_db):
    ws = _week()
    GO.suggest_weekly_goals(1, ws)
    assert WeeklyGoals.select().where(WeeklyGoals.student_id == 1).count() == 2
    # de novo no mesmo dia/semana não duplica
    GO.suggest_weekly_goals(1, ws)
    assert WeeklyGoals.select().where(WeeklyGoals.student_id == 1).count() == 2
    kinds = {g.kind for g in WeeklyGoals.select()}
    assert "dias_de_estudo" in kinds
    assert "concluir_modulos" in kinds     # sem revisão ativa -> a 2ª é concluir


def test_second_goal_is_reviews_when_active(seeded_db):
    ws = _week()
    ReviewSchedule.create(student_id=1, competency_id=1, due_date=datetime.date(2026, 7, 8),
                          interval_days=1, ease=2.5, status="agendada",
                          created_by="agent", created_at=datetime.datetime.now())
    GO.suggest_weekly_goals(1, ws)
    kinds = {g.kind for g in WeeklyGoals.select()}
    assert "revisoes_em_dia" in kinds


def test_progress_and_completion_awards_xp(seeded_db):
    ws = _week()
    # meta de 1 módulo; concede XP modulo_concluido na semana -> cumpre
    WeeklyGoals.create(student_id=1, week_start=ws, kind="concluir_modulos",
                       target=1, progress=0, status="aceita",
                       created_at=datetime.datetime.now())
    G.award(1, "modulo_concluido", "ova", 1, today=ws + datetime.timedelta(days=1))
    state = GO.goals_state(1, ws)
    meta = [g for g in state if g["kind"] == "concluir_modulos"][0]
    assert meta["progress"] == 1 and meta["status"] == "cumprida"
    # cumprir concedeu meta_semanal (+50)
    assert G.xp_total(1) >= 90   # 40 (modulo) + 50 (meta)


def test_accept_goal_route(client, auth, seeded_db):
    ws = G._week_start()
    g = WeeklyGoals.create(student_id=1, week_start=ws, kind="dias_de_estudo",
                           target=3, progress=0, status="sugerida",
                           created_at=datetime.datetime.now())
    resp = client.post("/goals/accept", data=json.dumps({"goal_id": g.goal_id}), headers=auth(1))
    assert resp.status_code == 200
    assert WeeklyGoals.get_by_id(g.goal_id).status == "aceita"


def test_goals_route_suggests_when_empty(client, auth, seeded_db):
    resp = client.get("/goals", headers=auth(1))
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["enabled"] is True
    assert len(body["goals"]) == 2


def test_goals_route_empty_when_flag_off(client, auth, seeded_db, monkeypatch):
    monkeypatch.setenv("EDUBOT_GAMIFICATION", "off")
    body = json.loads(client.get("/goals", headers=auth(1)).data)
    assert body["enabled"] is False and body["goals"] == []
