"""Fase 4d (A5) — senhas com hash PBKDF2 e upgrade-on-login do seed legado."""
import json

from edubot.api.auth import hash_password, is_hashed, verify_password
from edubot.data.models.students import Students


def _login(client, ra, password):
    return client.post("/login", data=json.dumps({"ra": ra, "password": password}),
                       content_type="application/json")


def test_hash_roundtrip():
    stored = hash_password("s3nha!")
    assert is_hashed(stored)
    assert verify_password("s3nha!", stored)
    assert not verify_password("errada", stored)


def test_legacy_plaintext_upgrades_on_login(client, seeded_db):
    # Seed guarda texto plano ("111"). Primeiro login funciona e converte.
    assert not is_hashed(Students.get_by_id(1).student_password)
    r = _login(client, "111", "111")
    assert r.status_code == 200 and "token" in json.loads(r.data.decode())
    stored = Students.get_by_id(1).student_password
    assert is_hashed(stored)
    # Segundo login verifica contra o hash (não mais texto plano).
    assert _login(client, "111", "111").status_code == 200
    # Hash não muda em logins subsequentes.
    assert Students.get_by_id(1).student_password == stored


def test_wrong_password_rejected_before_and_after_upgrade(client, seeded_db):
    assert _login(client, "111", "errada").status_code == 401
    _login(client, "111", "111")  # upgrade
    assert _login(client, "111", "errada").status_code == 401
    assert _login(client, "", "111").status_code == 401
