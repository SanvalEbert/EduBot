"""A.4 — ciclo de vida dos alertas do tutor: ack, auto-expiração e a dedup que
volta a funcionar depois do ack."""
import datetime
import json

from edubot.data.models.alerts import Alerts
from edubot.data.models.attempts import Attempts
from edubot.services.proactivity import (evaluate_student, expire_stale_alerts,
                                         ALERT_EXPIRY_DAYS)
from edubot.data.models.students import Students


def _make_alert(student_id=1, atype="trilha_minima", read=False, days_ago=0):
    return Alerts.create(
        student_id=student_id, type=atype, message="m", severity="alta",
        created_at=datetime.datetime.now() - datetime.timedelta(days=days_ago),
        read=read)


def test_ack_requires_tutor(client, auth, seeded_db):
    al = _make_alert()
    # aluno (1) não pode dar ack
    r = client.post("/tutor/alert/ack", headers=auth(1),
                    data=json.dumps({"alert_id": al.alert_id}))
    assert r.status_code == 403


def test_ack_marks_read_for_tutor(client, auth, seeded_db):
    al = _make_alert()
    r = client.post("/tutor/alert/ack", headers=auth(9),
                    data=json.dumps({"alert_id": al.alert_id}))
    assert r.status_code == 200
    assert Alerts.get_by_id(al.alert_id).read is True


def test_ack_unknown_alert_404(client, auth, seeded_db):
    r = client.post("/tutor/alert/ack", headers=auth(9),
                    data=json.dumps({"alert_id": 9999}))
    assert r.status_code == 404


def test_expire_stale_alerts(seeded_db):
    _make_alert(days_ago=ALERT_EXPIRY_DAYS + 1)          # antigo -> expira
    fresh = _make_alert(days_ago=0)                       # recente -> fica
    n = expire_stale_alerts()
    assert n == 1
    assert Alerts.get_by_id(fresh.alert_id).read is False


def test_dedup_reopens_after_ack(seeded_db):
    """A regressão que A.4 conserta: com o alerta pendente, a avaliação NÃO cria
    outro do mesmo tipo; depois do ack, ela volta a criar."""
    student = Students.get_by_id(1)
    # cria condição de risco: várias tentativas erradas (taxa de erro alta)
    for _ in range(4):
        Attempts.create(student_id=1, question_id=1, is_correct=False,
                        attempt_time=datetime.datetime.now())

    evaluate_student(student)
    first = Alerts.select().where(Alerts.student_id == 1).count()
    assert first >= 1

    # segunda avaliação com o alerta ainda aberto: dedup segura (não duplica)
    evaluate_student(student)
    assert Alerts.select().where((Alerts.student_id == 1) & (Alerts.read == False)).count() == first

    # tutor trata todos -> a próxima avaliação pode alertar de novo
    Alerts.update(read=True).where(Alerts.student_id == 1).execute()
    evaluate_student(student)
    assert Alerts.select().where((Alerts.student_id == 1) & (Alerts.read == False)).count() >= 1
