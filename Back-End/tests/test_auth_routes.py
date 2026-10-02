"""A.3 — rotas antes abertas agora exigem token/papel; rate-limit no login."""
import json


def test_question_all_requires_auth(client):
    assert client.get("/question/all").status_code == 401


def test_question_all_ok_with_token(client, auth):
    r = client.get("/question/all", headers=auth(1))
    assert r.status_code == 200
    assert isinstance(json.loads(r.data.decode()), list)


def test_student_by_course_requires_auth(client):
    assert client.get("/student/course/1").status_code == 401


def test_student_by_course_forbidden_for_aluno(client, auth):
    # aluno (student 1) não pode listar alunos do curso (PII/LGPD)
    assert client.get("/student/course/1", headers=auth(1)).status_code == 403


def test_student_by_course_ok_for_tutor(client, auth):
    # student 9 = tutor (is_admin=True, role=tutor no seed)
    r = client.get("/student/course/1", headers=auth(9))
    assert r.status_code == 200
    assert isinstance(json.loads(r.data.decode()), list)


def test_login_rate_limited_after_max_attempts(client):
    body = json.dumps({"ra": "111", "password": "errada"})
    # 5 tentativas dentro da janela são permitidas (retornam 401 = senha errada)
    for _ in range(5):
        assert client.post("/login", data=body, content_type="application/json").status_code == 401
    # a 6ª é barrada pelo rate-limit
    r = client.post("/login", data=body, content_type="application/json")
    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "60"
