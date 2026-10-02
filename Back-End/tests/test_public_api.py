"""API pública de integração (/api/v1) — chave, escopo e pseudonimização.

O que estes testes travam:
  1. Nenhum endpoint responde sem chave válida (401).
  2. Chave válida com escopo errado não vaza dado (403).
  3. Dado pessoal só sai com `students:pii` — este é o teste que impede uma
     regressão de LGPD passar despercebida.
  4. O cursor de paginação não pula nem repete linhas.
"""
import datetime
import json

import pytest

from edubot.api.apikey import pseudonym
from edubot.data.models.api_keys import ApiKeys
from edubot.data.models.learning_events import LearningEvents
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.student_mastery import StudentMastery


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
ENDPOINTS = [
    "/api/v1/ping",
    "/api/v1/catalog/ovas",
    "/api/v1/catalog/questions",
    "/api/v1/tracking/events",
    "/api/v1/tracking/progress",
    "/api/v1/tracking/sections",
    "/api/v1/metrics/mastery",
    "/api/v1/metrics/coverage",
    "/api/v1/students",
]


@pytest.mark.parametrize("url", ENDPOINTS)
def test_sem_chave_e_401(client, url):
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("url", ENDPOINTS)
def test_chave_inexistente_e_401(client, url):
    resp = client.get(url, headers={"X-API-Key": "ek_live_naoexiste"})
    assert resp.status_code == 401


def test_token_de_aluno_nao_serve_como_chave(client, auth):
    """Sessão de aluno e credencial de parceiro são universos separados."""
    assert client.get("/api/v1/catalog/ovas", headers=auth()).status_code == 401


def test_chave_revogada_e_401(client, api_key):
    headers = api_key("catalog:read", active=False)
    assert client.get("/api/v1/catalog/ovas", headers=headers).status_code == 401


def test_chave_expirada_e_401(client, api_key):
    ontem = datetime.datetime.now() - datetime.timedelta(days=1)
    headers = api_key("catalog:read", expires_at=ontem)
    assert client.get("/api/v1/catalog/ovas", headers=headers).status_code == 401


def test_chave_sem_validade_funciona(client, api_key):
    """expires_at NULL não pode ser confundido com expirada."""
    headers = api_key("catalog:read", expires_at=None)
    assert client.get("/api/v1/catalog/ovas", headers=headers).status_code == 200


def test_authorization_apikey_tambem_funciona(client, api_key):
    headers = api_key("catalog:read")
    alt = {"Authorization": f"ApiKey {headers['X-API-Key']}"}
    assert client.get("/api/v1/catalog/ovas", headers=alt).status_code == 200


def test_ping_nao_exige_escopo(client, api_key):
    resp = client.get("/api/v1/ping", headers=api_key())
    assert resp.status_code == 200
    assert json.loads(resp.data)["scopes"] == []


def test_uso_da_chave_e_contabilizado(client, api_key):
    headers = api_key("catalog:read")
    client.get("/api/v1/catalog/ovas", headers=headers)
    client.get("/api/v1/catalog/ovas", headers=headers)
    chave = ApiKeys.select().order_by(ApiKeys.key_id.desc()).first()
    assert chave.request_count == 2
    assert chave.last_used_at is not None


# ---------------------------------------------------------------------------
# Escopos
# ---------------------------------------------------------------------------
def test_escopo_errado_e_403(client, api_key):
    resp = client.get("/api/v1/tracking/events", headers=api_key("catalog:read"))
    assert resp.status_code == 403


def test_403_diz_qual_escopo_falta(client, api_key):
    resp = client.get("/api/v1/tracking/events", headers=api_key("catalog:read"))
    assert "tracking:read" in json.loads(resp.data)["error"]


def test_catalogo_nao_abre_rastreio(client, api_key):
    headers = api_key("catalog:read")
    assert client.get("/api/v1/catalog/ovas", headers=headers).status_code == 200
    assert client.get("/api/v1/tracking/progress", headers=headers).status_code == 403
    assert client.get("/api/v1/metrics/mastery", headers=headers).status_code == 403
    assert client.get("/api/v1/students", headers=headers).status_code == 403


def test_scopes_mostra_o_que_a_chave_tem(client, api_key):
    resp = client.get("/api/v1/scopes", headers=api_key("catalog:read"))
    por_nome = {s["scope"]: s["concedido"] for s in json.loads(resp.data)["scopes"]}
    assert por_nome["catalog:read"] is True
    assert por_nome["students:pii"] is False


# ---------------------------------------------------------------------------
# LGPD — dado pessoal só com students:pii
# ---------------------------------------------------------------------------
def test_alunos_sem_pii_nao_traz_nome_nem_ra(client, api_key):
    resp = client.get("/api/v1/students", headers=api_key("students:read"))
    assert resp.status_code == 200
    corpo = json.loads(resp.data)
    assert corpo["pii_incluido"] is False
    assert corpo["data"], "o seed tem alunos"
    for aluno in corpo["data"]:
        assert "student_name" not in aluno
        assert "ra" not in aluno
        assert "student_id" not in aluno
        assert len(aluno["subject_id"]) == 16


def test_alunos_com_pii_traz_nome_e_ra(client, api_key):
    resp = client.get("/api/v1/students", headers=api_key("students:read", "students:pii"))
    corpo = json.loads(resp.data)
    assert corpo["pii_incluido"] is True
    ana = [a for a in corpo["data"] if a.get("student_id") == 1][0]
    assert ana["student_name"] == "Ana Souza"
    assert ana["ra"] == "111"


def test_senha_nunca_sai_nem_com_pii(client, api_key):
    resp = client.get("/api/v1/students", headers=api_key("students:read", "students:pii"))
    assert "student_password" not in resp.get_data(as_text=True)
    assert "111" in resp.get_data(as_text=True)  # o RA sai; a senha, não


def test_pseudonimo_e_estavel_entre_endpoints(client, api_key, seeded_db):
    """O parceiro precisa cruzar evento com aluno sem saber quem é o aluno."""
    LearningEvents.create(student_id=1, verb="opened", object_type="ova", object_id=1,
                          occurred_at=datetime.datetime.now())
    headers = api_key("students:read", "tracking:read")
    alunos = json.loads(client.get("/api/v1/students", headers=headers).data)["data"]
    eventos = json.loads(client.get("/api/v1/tracking/events", headers=headers).data)["data"]
    assert eventos[0]["subject_id"] in {a["subject_id"] for a in alunos}
    assert eventos[0]["subject_id"] == pseudonym(1)


def test_texto_livre_do_evento_e_removido_sem_pii(client, api_key, seeded_db):
    """context.text de asked_tutor é conteúdo escrito pelo aluno."""
    LearningEvents.create(student_id=1, verb="asked_tutor", object_type="session",
                          context={"text": "nao entendi a questao 3", "response_ms": 900},
                          occurred_at=datetime.datetime.now())
    resp = client.get("/api/v1/tracking/events", headers=api_key("tracking:read"))
    evento = json.loads(resp.data)["data"][0]
    assert evento["context"]["text"] is None
    assert evento["context"]["response_ms"] == 900  # o resto do contexto continua


def test_texto_livre_sai_com_pii(client, api_key, seeded_db):
    LearningEvents.create(student_id=1, verb="asked_tutor", object_type="session",
                          context={"text": "nao entendi a questao 3"},
                          occurred_at=datetime.datetime.now())
    resp = client.get("/api/v1/tracking/events",
                      headers=api_key("tracking:read", "students:pii"))
    assert json.loads(resp.data)["data"][0]["context"]["text"] == "nao entendi a questao 3"


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
def test_gabarito_escondido_por_padrao(client, api_key):
    resp = client.get("/api/v1/catalog/questions", headers=api_key("catalog:read"))
    corpo = json.loads(resp.data)
    assert corpo["gabarito_incluido"] is False
    assert all("answer" not in q for q in corpo["data"])
    assert corpo["data"][0]["statement"] == "2+2?"


def test_gabarito_sai_quando_pedido(client, api_key):
    resp = client.get("/api/v1/catalog/questions?include_answer=1",
                      headers=api_key("catalog:read"))
    corpo = json.loads(resp.data)
    assert corpo["gabarito_incluido"] is True
    assert corpo["data"][0]["answer"] == "b"


def test_filtro_por_ova(client, api_key):
    resp = client.get("/api/v1/catalog/questions?ova_id=999", headers=api_key("catalog:read"))
    assert json.loads(resp.data)["count"] == 0


# ---------------------------------------------------------------------------
# Paginação por cursor
# ---------------------------------------------------------------------------
def test_cursor_percorre_tudo_sem_pular_nem_repetir(client, api_key, seeded_db):
    for i in range(7):
        LearningEvents.create(student_id=1, verb="opened", object_type="ova",
                              object_id=1, occurred_at=datetime.datetime.now())
    headers = api_key("tracking:read")
    vistos, cursor, paginas = [], None, 0
    while paginas < 10:
        url = "/api/v1/tracking/events?limit=3"
        if cursor is not None:
            url += f"&after_id={cursor}"
        corpo = json.loads(client.get(url, headers=headers).data)
        vistos += [e["event_id"] for e in corpo["data"]]
        cursor = corpo["next_after_id"]
        paginas += 1
        if cursor is None:
            break
    assert len(vistos) == 7
    assert len(set(vistos)) == 7
    assert vistos == sorted(vistos)


def test_limit_e_clampado_no_maximo(client, api_key, seeded_db):
    resp = client.get("/api/v1/tracking/events?limit=99999", headers=api_key("tracking:read"))
    assert resp.status_code == 200


def test_data_invalida_e_400(client, api_key):
    resp = client.get("/api/v1/tracking/events?since=ontem", headers=api_key("tracking:read"))
    assert resp.status_code == 400
    assert "since" in json.loads(resp.data)["error"]


def test_filtro_since_recorta(client, api_key, seeded_db):
    antigo = datetime.datetime.now() - datetime.timedelta(days=10)
    LearningEvents.create(student_id=1, verb="opened", object_type="ova",
                          object_id=1, occurred_at=antigo)
    LearningEvents.create(student_id=1, verb="completed", object_type="ova",
                          object_id=1, occurred_at=datetime.datetime.now())
    ontem = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    resp = client.get(f"/api/v1/tracking/events?since={ontem}",
                      headers=api_key("tracking:read"))
    corpo = json.loads(resp.data)
    assert corpo["count"] == 1
    assert corpo["data"][0]["verb"] == "completed"


# ---------------------------------------------------------------------------
# Rastreio e métricas
# ---------------------------------------------------------------------------
def test_progresso_traz_leitura_e_conclusao(client, api_key, seeded_db):
    OVAProgress.create(progress_id=1, student_id=1, ova_id=1, read_time=300,
                       perc_scrolled=85, completed=True,
                       last_access=datetime.datetime.now())
    resp = client.get("/api/v1/tracking/progress", headers=api_key("tracking:read"))
    linha = json.loads(resp.data)["data"][0]
    assert linha["read_time_seconds"] == 300
    assert linha["perc_scrolled"] == 85
    assert linha["completed"] is True
    assert linha["subject_id"] == pseudonym(1)
    assert "student_id" not in linha


def test_mastery_agrega_com_n_da_amostra(client, api_key, seeded_db):
    StudentMastery.create(student_id=1, competency_id=1, p_mastery=0.8, attempts_seen=4)
    StudentMastery.create(student_id=2, competency_id=1, p_mastery=0.4, attempts_seen=2)
    resp = client.get("/api/v1/metrics/mastery", headers=api_key("metrics:read"))
    linha = json.loads(resp.data)["data"][0]
    assert linha["competency_id"] == 1
    assert linha["dominio_medio"] == pytest.approx(0.6, abs=1e-4)
    assert linha["alunos"] == 2
    assert linha["tentativas"] == 6


def test_metricas_nao_expoem_individuo(client, api_key, seeded_db):
    StudentMastery.create(student_id=1, competency_id=1, p_mastery=0.8, attempts_seen=4)
    for url in ("/api/v1/metrics/mastery", "/api/v1/metrics/engagement",
                "/api/v1/metrics/coverage", "/api/v1/metrics/questions"):
        texto = client.get(url, headers=api_key("metrics:read")).get_data(as_text=True)
        assert "student_id" not in texto
        assert "subject_id" not in texto


def test_engajamento_conta_por_verbo(client, api_key, seeded_db):
    agora = datetime.datetime.now()
    LearningEvents.create(student_id=1, verb="opened", object_type="ova", object_id=1, occurred_at=agora)
    LearningEvents.create(student_id=2, verb="opened", object_type="ova", object_id=1, occurred_at=agora)
    LearningEvents.create(student_id=1, verb="completed", object_type="ova", object_id=1, occurred_at=agora)
    resp = client.get("/api/v1/metrics/engagement", headers=api_key("metrics:read"))
    por_verbo = {r["verb"]: r for r in json.loads(resp.data)["data"]}
    assert por_verbo["opened"]["eventos"] == 2
    assert por_verbo["opened"]["alunos"] == 2
    assert por_verbo["completed"]["eventos"] == 1


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------
def test_rate_limit_devolve_429(client, api_key, monkeypatch):
    import edubot.api.apikey as apikey_mod
    monkeypatch.setattr(apikey_mod, "RATE_LIMIT", 3)
    headers = api_key("catalog:read")
    codigos = [client.get("/api/v1/catalog/ovas", headers=headers).status_code
               for _ in range(5)]
    assert codigos[:3] == [200, 200, 200]
    assert codigos[3] == 429
