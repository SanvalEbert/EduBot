"""Plano 5 — detalhe do aluno para o professor (/tutor/student/<id>) e rollup
do gestor (/tutor/overview).

Cobre o escopo de segurança (staff-only + mesmo curso) e a agregação por assunto.
Roda em SQLite na memória sobre o seed do conftest (alunos 1 e 2, tutor 9,
assunto 1 = "Assunto", competência 1 com questões 1 e 2)."""
import datetime
import json

from edubot.data.models.answers import Answers
from edubot.data.models.attempts import Attempts

NOW = datetime.datetime.now()


def _seed_activity():
    # aluno 1: acerta q1 e erra q2 -> 1 acerto, 1 erro, 2 tentativas
    Attempts.create(student_id=1, question_id=1, is_correct=True, attempt_time=NOW)
    Attempts.create(student_id=1, question_id=2, is_correct=False, attempt_time=NOW)
    Answers.create(student_id=1, question_id=1)
    # aluno 2: erra q1 duas vezes -> taxa de erro 100% (em risco)
    Attempts.create(student_id=2, question_id=1, is_correct=False, attempt_time=NOW)
    Attempts.create(student_id=2, question_id=1, is_correct=False, attempt_time=NOW)


def test_tutor_student_detail_ok(client, auth, seeded_db):
    _seed_activity()
    resp = client.get("/tutor/student/1", headers=auth(9))  # 9 = tutor
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["estudante"]["ra"] == "111"
    comp = data["competencias"][0]
    # Plano 5 (17.1): competência traz o assunto
    assert comp["subject_id"] == 1
    assert comp["subject_nome"] == "Assunto"
    assert comp["acertos"] == 1
    assert comp["erros"] == 1


def test_tutor_student_detail_requires_staff(client, auth, seeded_db):
    resp = client.get("/tutor/student/2", headers=auth(1))  # aluno comum
    assert resp.status_code == 403


def test_tutor_student_detail_scope_404(client, auth, seeded_db):
    # tutor (role != aluno) e aluno inexistente -> 404 (não vaza existência)
    assert client.get("/tutor/student/9", headers=auth(9)).status_code == 404
    assert client.get("/tutor/student/99999", headers=auth(9)).status_code == 404


def test_tutor_overview(client, auth, seeded_db):
    _seed_activity()
    resp = client.get("/tutor/overview", headers=auth(9))
    assert resp.status_code == 200
    data = json.loads(resp.data)

    assert data["turma"]["alunos_ativos"] == 2
    assert data["turma"]["em_risco"] >= 1  # aluno 2 tem taxa de erro > 0.5

    # quiz da turma: 1 acerto (Answer do aluno 1), 3 erros (1 + 2), 4 tentativas
    assert data["quiz"]["acertos"] == 1
    assert data["quiz"]["erros"] == 3
    assert data["quiz"]["tentativas"] == 4

    assunto = [s for s in data["por_assunto"] if s["subject_id"] == 1][0]
    assert assunto["subject_nome"] == "Assunto"
    assert assunto["acertos"] == 1
    assert assunto["erros"] == 3
    assert assunto["tentativas"] == 4
    assert assunto["total_questoes"] == 2

    assert data["rastreamento"]["tentativas_quiz"] == 4


def test_tutor_overview_requires_staff(client, auth, seeded_db):
    assert client.get("/tutor/overview", headers=auth(1)).status_code == 403
