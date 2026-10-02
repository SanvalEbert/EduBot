"""E.4 (Plano 2) — painel de engajamento do tutor."""
import datetime
import json

import pytest

from edubot.data.models.attempts import Attempts
from edubot.data.models.consents import Consents
from edubot.data.models.learning_events import LearningEvents
from edubot.data.models.student_streak import StudentStreak


@pytest.fixture(autouse=True)
def _gami_on(monkeypatch):
    monkeypatch.setenv("EDUBOT_GAMIFICATION", "on")
    yield


def test_engagement_requires_staff(client, auth, seeded_db):
    assert client.get("/tutor/engagement", headers=auth(1)).status_code == 403


def test_engagement_shape_and_at_risk(client, auth, seeded_db):
    # torna aluno 1 "ativo" (tem tentativa) e prestes a perder a sequência
    Attempts.create(student_id=1, question_id=1, is_correct=True)
    y = datetime.date.today() - datetime.timedelta(days=1)
    StudentStreak.create(student_id=1, current_days=3, best_days=3,
                         last_activity_date=y, shield_used_on=None)
    Consents.create(student_id=1, purpose="ranking_turma", granted=True,
                    granted_at=datetime.datetime.now())

    resp = client.get("/tutor/engagement", headers=auth(9))
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["participacao_ranking"]["opt_in"] == 1
    assert "distribuicao_sequencia" in body
    assert "antes_depois" in body
    # aluno 1 estudou ontem e não hoje -> em risco
    assert any(r["student_id"] == 1 for r in body["em_risco"])


def test_engagement_companion_block(client, auth, seeded_db):
    # EX.4 (Plano 3): uso do companheiro vem de learning_events (verbos CP.2/4/5).
    Attempts.create(student_id=1, question_id=1, is_correct=True)  # torna ativo
    now = datetime.datetime.now()
    LearningEvents.create(student_id=1, verb="companion_spoke", object_type="ova", occurred_at=now)
    LearningEvents.create(student_id=1, verb="played", object_type="ova_section", occurred_at=now)
    LearningEvents.create(student_id=1, verb="played", object_type="ova_section", occurred_at=now)
    LearningEvents.create(student_id=1, verb="companion_explain", object_type="ova", occurred_at=now)
    LearningEvents.create(student_id=1, verb="companion_listened", object_type="ova", occurred_at=now)
    body = json.loads(client.get("/tutor/engagement", headers=auth(9)).data)
    c = body["companheiro"]
    assert c["alunos_ativos"] == 1                 # 1 aluno viu o companheiro falar
    assert c["secoes_ouvidas_semana"] == 2         # 2 "ouvir seção"
    assert c["explicacoes_semana"] == 1
    assert c["falas_ouvidas_semana"] == 1


def test_active_days_counts_distinct_days_not_events(client, auth, seeded_db):
    # AUDITORIA P2 (F1): 3 eventos em 2 dias distintos devem contar 2 DIAS
    # ativos, não 3 (o DISTINCT era sobre o timestamp, não sobre a data).
    Attempts.create(student_id=1, question_id=1, is_correct=True)  # torna ativo
    now = datetime.datetime.now()
    LearningEvents.create(student_id=1, verb="opened", object_type="ova",
                          occurred_at=now - datetime.timedelta(days=1, hours=2))
    LearningEvents.create(student_id=1, verb="answered", object_type="question",
                          occurred_at=now - datetime.timedelta(days=1, hours=1))
    LearningEvents.create(student_id=1, verb="opened", object_type="ova",
                          occurred_at=now - datetime.timedelta(hours=3))
    body = json.loads(client.get("/tutor/engagement", headers=auth(9)).data)
    assert body["antes_depois"]["dias_ativos_depois"] == 2.0
