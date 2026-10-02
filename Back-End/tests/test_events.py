"""D.1 — eventos de aprendizado (xAPI-lite)."""
import json

from edubot.data.models.learning_events import LearningEvents
from edubot.data.models.students import Students
from edubot.services.events import emit


def test_post_events_batch_accepted(client, auth):
    body = {"events": [
        {"verb": "opened", "object_type": "ova", "object_id": 1, "context": {"perc": 0}},
        {"verb": "played", "object_type": "resource", "object_id": 2,
         "context": {"seconds": 12}},
    ]}
    resp = client.post("/events", data=json.dumps(body), headers=auth())
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["accepted"] == 2 and data["errors"] == 0
    # student vem do token (id=1), nunca do payload
    assert LearningEvents.select().where(LearningEvents.student_id == 1).count() == 2


def test_post_events_single_object(client, auth):
    body = {"verb": "logged_in", "object_type": "session"}
    resp = client.post("/events", data=json.dumps(body), headers=auth())
    assert resp.status_code == 200
    assert json.loads(resp.data)["accepted"] == 1


def test_invalid_verb_counts_as_error(client, auth):
    body = {"events": [
        {"verb": "opened", "object_type": "ova", "object_id": 1},
        {"verb": "hackerman", "object_type": "ova", "object_id": 1},
    ]}
    resp = client.post("/events", data=json.dumps(body), headers=auth())
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["accepted"] == 1 and data["errors"] == 1


def test_all_invalid_batch_is_400(client, auth):
    body = {"events": [{"verb": "nope", "object_type": "ova"}]}
    resp = client.post("/events", data=json.dumps(body), headers=auth())
    assert resp.status_code == 400


def test_batch_over_limit_is_400(client, auth):
    body = {"events": [{"verb": "opened", "object_type": "ova", "object_id": 1}
                       for _ in range(51)]}
    resp = client.post("/events", data=json.dumps(body), headers=auth())
    assert resp.status_code == 400


def test_events_require_auth(client):
    resp = client.post("/events", data=json.dumps({"verb": "opened",
                       "object_type": "ova"}), headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_answer_emits_answered_event(client, auth):
    # Responder uma questão grava um evento `answered` com correct/response_ms.
    body = {"question_id": 1, "selected": "b", "response_ms": 4200}
    resp = client.post("/question/answer", data=json.dumps(body), headers=auth())
    assert resp.status_code == 200
    ev = (LearningEvents
          .select()
          .where((LearningEvents.student_id == 1) & (LearningEvents.verb == "answered"))
          .first())
    assert ev is not None
    assert ev.context["correct"] is True
    assert ev.context["response_ms"] == 4200


def test_emit_drops_tutor_text_without_consent(seeded_db):
    # D.5: sem consentimento ia_sobre_dados, o texto da pergunta ao tutor não é
    # persistido (só metadados).
    student = Students.get_by_id(1)
    ev = emit(student, "asked_tutor", "ova", 1, text="como funciona X?", session_id="s1")
    assert ev is not None
    assert ev.context["text"] is None
    assert ev.context["session_id"] == "s1"


def test_emit_keeps_tutor_text_with_consent(seeded_db):
    from edubot.services.consents import set_consent
    student = Students.get_by_id(1)
    set_consent(student, "ia_sobre_dados", True)
    ev = emit(student, "asked_tutor", "ova", 1, text="como funciona X?")
    assert ev.context["text"] == "como funciona X?"


def test_parse_dt_converts_utc_to_local():
    # AUDITORIA E1-6: o front manda toISOString() (UTC, sufixo Z); gravar o
    # relógio UTC como hora local deslocaria o evento (3h no Brasil). O parse
    # converte para o fuso local antes de descartar o tzinfo.
    import datetime
    from edubot.services.events import _parse_dt

    parsed = _parse_dt("2026-07-10T12:00:00.000Z")
    expected = (datetime.datetime(2026, 7, 10, 12, 0, 0,
                                  tzinfo=datetime.timezone.utc)
                .astimezone().replace(tzinfo=None))
    assert parsed == expected
    # naive continua passando direto; lixo vira None (usa "agora")
    assert _parse_dt("2026-07-10T09:00:00") == datetime.datetime(2026, 7, 10, 9, 0, 0)
    assert _parse_dt("not-a-date") is None


def test_tutor_chat_emits_asked_tutor(client, auth):
    # D.1/B.4: a pergunta ao tutor vira evento `asked_tutor` no backend; sem o
    # consentimento ia_sobre_dados, o texto é minimizado (None) — mas o evento
    # (metadado) existe e conta como sinal.
    body = {"ova_id": 1, "context": "Material do OVA sobre listas.",
            "messages": [{"role": "user", "content": "o que é uma lista encadeada?"}]}
    resp = client.post("/edubot/tutor-chat", data=json.dumps(body), headers=auth())
    assert resp.status_code == 200
    ev = (LearningEvents
          .select()
          .where((LearningEvents.student_id == 1) &
                 (LearningEvents.verb == "asked_tutor"))
          .first())
    assert ev is not None
    assert ev.object_id == 1
    assert ev.context["text"] is None  # sem consentimento -> minimizado


def test_ova_completion_emits_completed(client, auth):
    # D.1: a TRANSIÇÃO de conclusão do OVA emite `completed` (uma vez só).
    body = {"ova_id": 1, "seconds_delta": 30, "perc_scrolled": 95, "completed": True}
    assert client.post("/progress/ova", data=json.dumps(body), headers=auth()).status_code == 200
    # segundo sync já concluído: NÃO emite de novo (só a transição)
    assert client.post("/progress/ova", data=json.dumps(body), headers=auth()).status_code == 200
    events = (LearningEvents
              .select()
              .where((LearningEvents.student_id == 1) &
                     (LearningEvents.verb == "completed")))
    assert events.count() == 1
    assert events.first().object_id == 1
