"""D.5 — consentimento (LGPD) e direitos do titular."""
import json

from edubot.data.models.alerts import Alerts
from edubot.data.models.students import Students
from edubot.services.consents import has_consent, set_consent, current_consents


def test_get_consents_defaults(client, auth):
    resp = client.get("/consents", headers=auth())
    assert resp.status_code == 200
    by_purpose = {c["purpose"]: c for c in json.loads(resp.data)["consents"]}
    # tracking é informado/execução de contrato -> default concedido
    assert by_purpose["tracking_pedagogico"]["granted"] is True
    assert by_purpose["tracking_pedagogico"]["opt_in"] is False
    # os opt-in nascem não concedidos
    assert by_purpose["ia_sobre_dados"]["granted"] is False
    assert by_purpose["imagem_voz"]["granted"] is False


def test_post_consent_grants_optin(client, auth):
    resp = client.post("/consents",
                       data=json.dumps({"purpose": "ia_sobre_dados", "granted": True}),
                       headers=auth())
    assert resp.status_code == 200
    student = Students.get_by_id(1)
    assert has_consent(student, "ia_sobre_dados") is True


def test_tracking_cannot_be_revoked(seeded_db):
    student = Students.get_by_id(1)
    set_consent(student, "tracking_pedagogico", False)  # tentativa de revogar
    assert has_consent(student, "tracking_pedagogico") is True


def test_revoke_optin(seeded_db):
    student = Students.get_by_id(1)
    set_consent(student, "ia_sobre_dados", True)
    assert has_consent(student, "ia_sobre_dados") is True
    set_consent(student, "ia_sobre_dados", False)
    assert has_consent(student, "ia_sobre_dados") is False
    row = [c for c in current_consents(student) if c["purpose"] == "ia_sobre_dados"][0]
    assert row["revoked_at"] is not None


def test_invalid_purpose_400(client, auth):
    resp = client.post("/consents",
                       data=json.dumps({"purpose": "vender_dados", "granted": True}),
                       headers=auth())
    assert resp.status_code == 400


def test_delete_request_creates_admin_alert(client, auth):
    resp = client.post("/student/me/delete-request", headers=auth())
    assert resp.status_code == 200
    alert = Alerts.get_or_none((Alerts.student_id == 1) &
                               (Alerts.type == "delete_request"))
    assert alert is not None
    assert alert.severity == "alta"


def test_delete_request_idempotent(client, auth):
    client.post("/student/me/delete-request", headers=auth())
    client.post("/student/me/delete-request", headers=auth())
    assert Alerts.select().where((Alerts.student_id == 1) &
                                 (Alerts.type == "delete_request")).count() == 1


def test_consents_require_auth(client):
    assert client.get("/consents").status_code == 401
