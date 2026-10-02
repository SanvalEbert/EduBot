"""A.7 — controle de acesso das rotas de tutor (papel) e escopo de turma."""
import json


def test_turma_forbidden_for_aluno(client, auth):
    assert client.get("/tutor/turma", headers=auth(1)).status_code == 403


def test_alerts_forbidden_for_aluno(client, auth):
    assert client.get("/tutor/alerts", headers=auth(1)).status_code == 403


def test_evaluate_forbidden_for_aluno(client, auth):
    assert client.post("/tutor/evaluate", headers=auth(1)).status_code == 403


def test_turma_ok_for_tutor(client, auth):
    r = client.get("/tutor/turma", headers=auth(9))  # student 9 = tutor
    assert r.status_code == 200
    assert "alunos" in json.loads(r.data.decode())


def test_evaluate_requires_auth(client):
    assert client.post("/tutor/evaluate").status_code == 401
