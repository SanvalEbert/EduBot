"""Etapa 8 (Plano 2) — gamificação: XP anti-farm, nível, sequência, conquistas, ranking."""
import datetime
import json

import pytest

from edubot.data.models.consents import Consents
from edubot.data.models.student_mastery import StudentMastery
from edubot.data.models.students import Students
from edubot.data.models.xp_events import XpEvents
from edubot.services import gamification as G


@pytest.fixture(autouse=True)
def _gami_on(monkeypatch):
    monkeypatch.setenv("EDUBOT_GAMIFICATION", "on")
    yield


# --- XP anti-farm ----------------------------------------------------------
def test_award_once_per_object_per_day(seeded_db):
    assert G.award(1, "modulo_concluido", "ova", 1) == 40
    # repetir o MESMO objeto no mesmo dia não concede de novo (dedup)
    assert G.award(1, "modulo_concluido", "ova", 1) == 0
    assert G.xp_total(1) == 40


def test_daily_cap_enforced(seeded_db):
    # pergunta_ao_tutor: teto 2/dia (objetos diferentes contam)
    assert G.award(1, "pergunta_ao_tutor", "ova", 1) == 5
    assert G.award(1, "pergunta_ao_tutor", "ova", 2) == 5
    assert G.award(1, "pergunta_ao_tutor", "ova", 3) == 0   # 3ª barrada pelo teto
    assert G.xp_total(1) == 10


def test_objectless_rule_once_per_day(seeded_db):
    assert G.award(1, "dia_de_estudo") == 10
    assert G.award(1, "dia_de_estudo") == 0


def test_flag_off_is_noop(seeded_db, monkeypatch):
    monkeypatch.setenv("EDUBOT_GAMIFICATION", "off")
    assert G.award(1, "modulo_concluido", "ova", 1) == 0
    assert XpEvents.select().count() == 0


def test_level_curve(seeded_db):
    assert G.level_from_xp(0) == 1
    assert G.level_from_xp(59) == 1
    assert G.level_from_xp(60) == 2         # base 60 -> nível 2
    assert G.level_from_xp(240) == 3        # 60*4 -> nível 3
    prog = G.level_progress(60)
    assert prog["level"] == 2 and prog["into_level"] == 0


# --- Sequência (streak) com escudo -----------------------------------------
def test_streak_grows_on_consecutive_days(seeded_db):
    d = datetime.date(2026, 7, 6)
    assert G.update_streak(1, d) == 1
    assert G.update_streak(1, d) == 1                       # 2x no mesmo dia: idempotente
    assert G.update_streak(1, d + datetime.timedelta(days=1)) == 2
    assert G.update_streak(1, d + datetime.timedelta(days=2)) == 3


def test_shield_covers_single_gap_once_per_week(seeded_db):
    d = datetime.date(2026, 7, 6)   # segunda
    G.update_streak(1, d)
    G.update_streak(1, d + datetime.timedelta(days=1))      # terça -> 2
    # pula quarta; volta quinta: escudo cobre 1 dia -> segue em 3
    assert G.update_streak(1, d + datetime.timedelta(days=3)) == 3
    # pula sexta; volta sábado na MESMA semana: escudo já usado -> zera
    assert G.update_streak(1, d + datetime.timedelta(days=5)) == 1


def test_streak_resets_on_large_gap(seeded_db):
    d = datetime.date(2026, 7, 6)
    G.update_streak(1, d)
    G.update_streak(1, d + datetime.timedelta(days=1))
    # 5 dias depois (buraco grande): zera, mas best fica
    assert G.update_streak(1, d + datetime.timedelta(days=6)) == 1
    st = G.streak_state(1, d + datetime.timedelta(days=6))
    assert st["best_days"] == 2


def test_streak_display_respects_shield(seeded_db):
    # AUDITORIA P2 (F2): última atividade ANTEONTEM + escudo disponível -> o
    # display MANTÉM a chama (é o caso que update_streak preservaria hoje).
    d = datetime.date(2026, 7, 6)
    G.update_streak(1, d)
    G.update_streak(1, d + datetime.timedelta(days=1))       # streak 2 (terça)
    quinta = d + datetime.timedelta(days=3)                  # pulou quarta
    assert G.streak_state(1, quinta)["current_days"] == 2    # escudo segura o display
    # com o escudo JÁ USADO na semana, o display zera de verdade
    from edubot.data.models.student_streak import StudentStreak
    StudentStreak.update(shield_used_on=d + datetime.timedelta(days=2)).where(
        StudentStreak.student_id == 1).execute()
    assert G.streak_state(1, quinta)["current_days"] == 0


def test_participate_rejects_duplicate_nickname_in_course(client, auth, seeded_db):
    # AUDITORIA P2 (F5): apelido é identidade pública no ranking — outro aluno
    # da turma não pode usar o mesmo (case-insensitive).
    Students.update(nickname="Rex").where(Students.student_id == 2).execute()
    resp = client.post("/gamification/participate",
                       data=json.dumps({"nickname": "rex"}), headers=auth(1))
    assert resp.status_code == 409
    # apelido livre continua funcionando
    ok = client.post("/gamification/participate",
                     data=json.dumps({"nickname": "Faisca"}), headers=auth(1))
    assert ok.status_code == 200


# --- Conquistas ------------------------------------------------------------
def test_achievement_primeiro_modulo(seeded_db):
    G.award(1, "modulo_concluido", "ova", 1)
    newly = G.check_achievements(1)
    assert "primeiro_modulo" in newly
    # idempotente: não desbloqueia de novo
    assert "primeiro_modulo" not in G.check_achievements(1)


def test_achievement_mestre_competencia(seeded_db):
    StudentMastery.create(student_id=1, competency_id=1, p_mastery=0.85,
                          attempts_seen=5, updated_at=datetime.datetime.now())
    assert "mestre_competencia" in G.check_achievements(1)


# --- Ranking opt-in --------------------------------------------------------
def _grant_ranking(sid, nick):
    Students.update(nickname=nick).where(Students.student_id == sid).execute()
    Consents.create(student_id=sid, purpose="ranking_turma", granted=True,
                    granted_at=datetime.datetime.now())


def test_leaderboard_lists_only_opted_in(seeded_db):
    # aluno 1 e 2 ganham XP na semana; só o 2 faz opt-in
    G.award(1, "modulo_concluido", "ova", 1)
    G.award(2, "modulo_concluido", "ova", 1)
    _grant_ranking(2, "Bia")
    board = G.leaderboard(Students.get_by_id(1))
    apelidos = [t["apelido"] for t in board["top"]]
    assert apelidos == ["Bia"]                 # 1 não participa -> não listado
    assert board["participando"] is False
    assert board["me"]["xp_semana"] == 40      # mas vê a própria posição
    assert board["me"]["rank"] is not None


def test_participate_route_sets_nickname_and_consent(client, auth, seeded_db):
    resp = client.post("/gamification/participate",
                       data=json.dumps({"nickname": "Rex"}), headers=auth(1))
    assert resp.status_code == 200
    assert Students.get_by_id(1).nickname == "Rex"
    from edubot.services.consents import has_consent
    assert has_consent(1, "ranking_turma") is True


def test_participate_requires_nickname(client, auth, seeded_db):
    resp = client.post("/gamification/participate",
                       data=json.dumps({"nickname": "x"}), headers=auth(1))
    assert resp.status_code == 400


def test_me_route_shape(client, auth, seeded_db):
    G.award(1, "modulo_concluido", "ova", 1)
    resp = client.get("/gamification/me", headers=auth(1))
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["enabled"] is True
    assert body["xp_total"] == 40
    assert body["level"] >= 1
    assert any(a["id"] == "primeiro_modulo" for a in body["achievements"])


# --- Gancho ponta a ponta (answer concede XP e devolve no payload) ---------
def test_answer_awards_xp_and_returns_it(client, auth, seeded_db):
    body = {"question_id": 1, "selected": "b"}
    resp = client.post("/question/answer", data=json.dumps(body), headers=auth(1))
    assert resp.status_code == 200
    gami = json.loads(resp.data)["gamification"]
    assert gami is not None
    # respondeu -> dia_de_estudo (10); é a única questão respondida, mas o OVA tem
    # 2 questões no seed -> quiz_do_modulo ainda não; então xp = 10
    assert gami["xp_awarded"] >= 10
    assert gami["streak"] == 1
