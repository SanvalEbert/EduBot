"""A1 — tempo de leitura por delta acumulado no servidor."""
import json

from edubot.data.models.ova_progress import OVAProgress


def _post(client, headers, body):
    return client.post("/progress/ova", headers=headers, data=json.dumps(body))


def test_read_time_accumulates_across_syncs(client, auth):
    h = auth(1)
    _post(client, h, {"ova_id": 1, "seconds_delta": 30, "perc_scrolled": 10})
    _post(client, h, {"ova_id": 1, "seconds_delta": 45, "perc_scrolled": 5})
    row = OVAProgress.get(OVAProgress.student_id == 1, OVAProgress.ova_id == 1)
    # Antes o backend fazia max() -> 45; agora acumula -> 75
    assert row.read_time == 75


def test_perc_scrolled_is_high_water_mark(client, auth):
    h = auth(1)
    _post(client, h, {"ova_id": 1, "seconds_delta": 5, "perc_scrolled": 80})
    _post(client, h, {"ova_id": 1, "seconds_delta": 5, "perc_scrolled": 20})
    row = OVAProgress.get(OVAProgress.student_id == 1, OVAProgress.ova_id == 1)
    assert row.perc_scrolled == 80


def test_legacy_absolute_read_time_still_supported(client, auth):
    h = auth(1)
    # cliente legado manda read_time absoluto (sem seconds_delta) -> max()
    _post(client, h, {"ova_id": 1, "read_time": 100, "perc_scrolled": 10})
    _post(client, h, {"ova_id": 1, "read_time": 60, "perc_scrolled": 10})
    row = OVAProgress.get(OVAProgress.student_id == 1, OVAProgress.ova_id == 1)
    assert row.read_time == 100


def test_unknown_ova_returns_400(client, auth):
    r = _post(client, auth(1), {"ova_id": 999, "seconds_delta": 5})
    assert r.status_code == 400


# A.6 — o upsert acumula read_time NO BANCO (COALESCE(read_time,0)+delta). Estes
# testam a robustez do delta e a atomicidade da acumulação.
def test_negative_delta_is_clamped_to_zero(client, auth):
    h = auth(1)
    _post(client, h, {"ova_id": 1, "seconds_delta": 40, "perc_scrolled": 10})
    _post(client, h, {"ova_id": 1, "seconds_delta": -100, "perc_scrolled": 10})
    row = OVAProgress.get(OVAProgress.student_id == 1, OVAProgress.ova_id == 1)
    assert row.read_time == 40  # delta negativo vira 0, não retrocede


def test_non_numeric_delta_returns_400(client, auth):
    r = _post(client, auth(1), {"ova_id": 1, "seconds_delta": "abc"})
    assert r.status_code == 400


def test_accumulation_is_atomic_on_existing_row(client, auth):
    # Simula o efeito de acumular sobre a linha atual do banco (não sobre um
    # valor pré-lido em memória): dois deltas somam mesmo partindo de um estado
    # já persistido por outra escrita.
    h = auth(1)
    _post(client, h, {"ova_id": 1, "seconds_delta": 10})
    # escrita "externa" direta no banco entre os dois syncs
    OVAProgress.update(read_time=1000).where(
        (OVAProgress.student_id == 1) & (OVAProgress.ova_id == 1)).execute()
    _post(client, h, {"ova_id": 1, "seconds_delta": 5})
    row = OVAProgress.get(OVAProgress.student_id == 1, OVAProgress.ova_id == 1)
    # a 2ª acumulação parte do valor NO BANCO (1000), não do pré-lido (10) -> 1005
    assert row.read_time == 1005
