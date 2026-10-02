"""Plano de Rastreabilidade — testes das Fases 0, 1 e 2.

Cobrem exatamente os defeitos que a auditoria apontou:
  P1  verbos do companheiro/seção eram DESCARTADOS pelo enum (painel do professor
      mostrava zero para sempre);
  P2  vídeo reportava POSIÇÃO como se fosse consumo (seek marcava 100%);
  P5  não havia rastreio por seção (não dava para saber ONDE o aluno travou).
"""
import json

from edubot.data.models.ova_section_progress import OVASectionProgress
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.resources import Resources
from edubot.services.media import merge_bitmap, normalize_bitmap


# --- Fase 0: os eventos que o front emitia e o backend jogava fora ----------

def test_verbos_do_companheiro_sao_aceitos(client, auth):
    """P1: antes estes verbos não estavam no enum e o lote inteiro virava erro."""
    resp = client.post("/events", json={"events": [
        {"verb": "companion_spoke", "object_type": "ova", "object_id": 1},
        {"verb": "companion_listened", "object_type": "ova", "object_id": 1},
        {"verb": "companion_dismissed", "object_type": "ova", "object_id": 1},
        {"verb": "companion_explain", "object_type": "ova", "object_id": 1},
    ]}, headers=auth(1))
    assert resp.status_code == 200
    assert json.loads(resp.data) == {"accepted": 4, "errors": 0}


def test_evento_de_secao_de_ova_e_aceito(client, auth):
    """P1: `ova_section` não existia em OBJECT_TYPES — o TTS de seção sumia."""
    resp = client.post("/events", json={"events": [
        {"verb": "played", "object_type": "ova_section", "object_id": 1},
        {"verb": "section_enter", "object_type": "ova_section", "object_id": 1},
        {"verb": "section_exit", "object_type": "ova_section", "object_id": 1},
        {"verb": "idle_start", "object_type": "session"},
        {"verb": "rate_changed", "object_type": "resource", "object_id": 1},
    ]}, headers=auth(1))
    assert json.loads(resp.data)["accepted"] == 5


def test_verbo_invalido_continua_rejeitado(client, auth):
    """O enum não virou um vale-tudo: o que não é sinal conhecido segue barrado."""
    resp = client.post("/events", json={"events": [
        {"verb": "coisa_inventada", "object_type": "ova", "object_id": 1},
    ]}, headers=auth(1))
    assert resp.status_code == 400


# --- Fase 1: consumo real de vídeo ------------------------------------------

def test_bitmap_normaliza_e_faz_or():
    assert normalize_bitmap("11") == "11" + "0" * 98
    assert normalize_bitmap("") is None
    merged, perc = merge_bitmap("1" + "0" * 99, "01" + "0" * 98)
    assert merged.startswith("11")
    assert perc == 2


def _video_resource():
    return Resources.create(resource_id=1, ova_id=1, resource_type="video",
                            resource_title="Vídeo 1", resource_url="http://v",
                            media_type="mp4", duration_seconds=100)


def test_seek_nao_infla_cobertura(client, auth):
    """P2 — o coração da correção: pular para o fim NÃO é assistir.

    O cliente manda posição 99 (perc_consumed alto), mas o bitmap só tem 2
    baldes acesos: a cobertura tem de refletir os 2%, não os 99%."""
    _video_resource()
    resp = client.post("/progress/resource", json={
        "resource_id": 1,
        "perc_consumed": 99,               # posição alcançada (legado)
        "coverage_bitmap": "11" + "0" * 98,  # só 2% realmente percorridos
        "watched_seconds_delta": 2,
        "last_position_s": 99,
    }, headers=auth(1))
    assert resp.status_code == 200

    rp = ResourceProgress.get()
    assert rp.coverage_perc == 2
    assert rp.watched_seconds == 2
    assert rp.completed is False          # 2% não conclui
    assert rp.last_position_seconds == 99  # ponto de abandono preservado


def test_watched_seconds_acumula_entre_sessoes(client, auth):
    """O tempo assistido soma (não é max), como o read_time do OVA."""
    _video_resource()
    for _ in range(3):
        client.post("/progress/resource", json={
            "resource_id": 1, "watched_seconds_delta": 10
        }, headers=auth(1))
    assert ResourceProgress.get().watched_seconds == 30


def test_cobertura_alta_conclui_o_video(client, auth):
    _video_resource()
    client.post("/progress/resource", json={
        "resource_id": 1, "coverage_bitmap": "1" * 95 + "0" * 5
    }, headers=auth(1))
    rp = ResourceProgress.get()
    assert rp.coverage_perc == 95
    assert rp.completed is True


def test_payload_legado_continua_funcionando(client, auth):
    """Degradação segura: um front antigo (sem os campos novos) não quebra."""
    _video_resource()
    resp = client.post("/progress/resource", json={
        "resource_id": 1, "perc_consumed": 50, "seconds_consumed": 30
    }, headers=auth(1))
    assert resp.status_code == 200
    rp = ResourceProgress.get()
    assert rp.perc_consumed == 50
    assert rp.coverage_perc == 0


# --- Fase 2: leitura por seção ----------------------------------------------

def test_progresso_por_secao_acumula_deltas(client, auth):
    """P5 — o dado que responde 'onde o aluno travou'."""
    payload = {"ova_id": 1, "sections": [
        {"section_id": "intro", "section_index": 0, "seconds_delta": 20,
         "max_scroll_perc": 40, "visits_delta": 1},
        {"section_id": "conclusao", "section_index": 1, "seconds_delta": 5,
         "max_scroll_perc": 10, "visits_delta": 1},
    ]}
    assert client.post("/progress/ova-section", json=payload, headers=auth(1)).status_code == 200
    # segundo sync: soma nos mesmos registros (não sobrescreve)
    client.post("/progress/ova-section", json={"ova_id": 1, "sections": [
        {"section_id": "intro", "section_index": 0, "seconds_delta": 10,
         "max_scroll_perc": 90, "visits_delta": 1},
    ]}, headers=auth(1))

    intro = OVASectionProgress.get(OVASectionProgress.section_id == "intro")
    assert intro.active_seconds == 30      # 20 + 10 (delta acumulado)
    assert intro.max_scroll_perc == 90     # marca d'água
    assert intro.visits == 2               # releitura detectada
    assert OVASectionProgress.select().count() == 2


def test_secao_de_ova_inexistente_da_400(client, auth):
    resp = client.post("/progress/ova-section",
                       json={"ova_id": 999, "sections": []}, headers=auth(1))
    assert resp.status_code == 400


def test_item_invalido_nao_derruba_o_lote(client, auth):
    """Mesma política do /events: um item ruim é ignorado, o resto grava."""
    resp = client.post("/progress/ova-section", json={"ova_id": 1, "sections": [
        {"section_id": "", "seconds_delta": 10},          # sem id -> ignorado
        {"section_id": "boa", "seconds_delta": 7, "section_index": 1,
         "max_scroll_perc": 50, "visits_delta": 1},
    ]}, headers=auth(1))
    assert json.loads(resp.data)["saved"] == 1
    assert OVASectionProgress.get().section_id == "boa"


def test_secao_exige_autenticacao(client, auth):
    assert client.post("/progress/ova-section", json={"ova_id": 1, "sections": []}).status_code == 401
