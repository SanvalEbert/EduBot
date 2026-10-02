"""A13 — proatividade: o EduBot age por evento, sem clique do aluno."""
import datetime
import json

from edubot.data.models.attempts import Attempts
from edubot.data.models.interventions import Interventions


def _answer(client, headers, qid, selected):
    return client.post("/question/answer", headers=headers,
                       data=json.dumps({"question_id": qid, "selected": selected}))


def _pending(student_id=1):
    return (Interventions
            .select()
            .where((Interventions.student_id == student_id) &
                   (Interventions.result == "pendente"))
            .count())


def test_wrong_answer_creates_intervention_without_click(client, auth):
    assert _pending(1) == 0
    _answer(client, auth(1), 1, "a")  # gabarito é "b" -> errada
    # O agente avaliou as regras na hora e materializou uma intervenção.
    assert _pending(1) >= 1


def test_correct_only_answer_does_not_trigger(client, auth):
    _answer(client, auth(1), 1, "b")  # correta -> sem gatilho de risco
    assert _pending(1) == 0


def test_ova_completion_triggers_evaluation(client, auth):
    r = client.post("/progress/ova", headers=auth(1),
                    data=json.dumps({"ova_id": 1, "seconds_delta": 30,
                                     "perc_scrolled": 95, "completed": True}))
    assert r.status_code == 200
    assert _pending(1) >= 1


def test_interventions_endpoint_lists_and_ack(client, auth):
    _answer(client, auth(1), 1, "a")  # cria intervenção
    r = client.get("/edubot/interventions", headers=auth(1))
    body = json.loads(r.data.decode())
    assert len(body["interventions"]) >= 1
    iid = body["interventions"][0]["intervention_id"]

    # marca como lida -> some da lista de não lidas
    r = client.post("/edubot/intervention/ack", headers=auth(1),
                    data=json.dumps({"intervention_id": iid}))
    assert r.status_code == 200
    r = client.get("/edubot/interventions", headers=auth(1))
    ids = [i["intervention_id"] for i in json.loads(r.data.decode())["interventions"]]
    assert iid not in ids


def test_ack_only_own_intervention(client, auth):
    _answer(client, auth(1), 1, "a")
    iid = json.loads(client.get("/edubot/interventions", headers=auth(1)).data.decode())["interventions"][0]["intervention_id"]
    # aluno 2 não pode marcar a intervenção do aluno 1
    r = client.post("/edubot/intervention/ack", headers=auth(2),
                    data=json.dumps({"intervention_id": iid}))
    assert r.status_code == 404


def test_dedup_no_duplicate_pending_same_type(client, auth):
    _answer(client, auth(1), 1, "a")
    _answer(client, auth(1), 2, "b")  # gabarito q2 é "a" -> outra errada
    # Mesmo com dois erros, não deve haver duas intervenções pendentes do mesmo tipo/dia.
    types = [it.type for it in Interventions.select().where(
        (Interventions.student_id == 1) & (Interventions.result == "pendente"))]
    assert len(types) == len(set(types))


def test_run_class_evaluation_scans_active_students(seeded_db):
    from edubot.services.proactivity import run_class_evaluation
    # Sem atividade nenhuma, ninguém é avaliado.
    assert run_class_evaluation() == 0
    # Dá atividade ao aluno 1 -> passa a ser varrido e ganha intervenção.
    Attempts.create(student_id=1, question_id=1, is_correct=False,
                    attempt_time=datetime.datetime.now())
    assert run_class_evaluation() >= 1
    assert _pending(1) >= 1


def test_scheduler_off_by_default(monkeypatch):
    from edubot.services import scheduler
    monkeypatch.delenv("EDUBOT_SCHEDULER", raising=False)
    scheduler._scheduler = None
    # Sem EDUBOT_SCHEDULER=on, não inicia nada (não roda em import/teste).
    assert scheduler.start_scheduler() is None


def test_trigger_guard_skips_when_already_notified_today(client, auth, seeded_db):
    # Guard de custo (A9): com intervenção pendente de hoje, o gatilho por
    # evento não remonta o perfil (retorna None sem avaliar).
    from edubot.data.models.students import Students
    from edubot.services.proactivity import trigger_evaluation
    _answer(client, auth(1), 1, "a")          # primeiro erro -> cria pendente
    before = _pending(1)
    assert trigger_evaluation(Students.get_by_id(1)) is None
    assert _pending(1) == before


def test_tutor_turma_uses_multisignal_inactivity(client, auth):
    import datetime as dt
    from edubot.data.models.ova_progress import OVAProgress
    # Aluno 1 só tem leitura (sem linhas em `interactions`).
    OVAProgress.create(student_id=1, ova_id=1, read_time=60, perc_scrolled=50,
                      completed=False, last_access=dt.datetime.now())
    r = client.get("/tutor/turma", headers=auth(9))  # aluno 9 = tutor
    turma = json.loads(r.data.decode())["alunos"]
    aluno1 = next(a for a in turma if a["student_id"] == 1)
    # A cópia antiga (só interactions) devolveria None; multi-sinal devolve 0.
    assert aluno1["dias_sem_acesso"] == 0


def test_progress_invalid_numeric_returns_400(client, auth):
    r = client.post("/progress/ova", headers=auth(1),
                    data=json.dumps({"ova_id": 1, "seconds_delta": "abc"}))
    assert r.status_code == 400
