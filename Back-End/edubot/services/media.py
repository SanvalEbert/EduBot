"""Consumo real de mídia (Plano de Rastreabilidade — Fase 1).

O player antigo reportava a POSIÇÃO máxima como se fosse consumo: um seek para o
fim marcava 100% sem o aluno assistir nada (auditoria P2). Aqui mora a regra que
torna a métrica honesta: a linha do tempo é dividida em `BITMAP_SIZE` baldes e um
balde só acende quando a reprodução passa por ele. Seek não acende balde.

O cliente envia o bitmap ACUMULADO da sessão (não um delta) e o servidor faz OR
com o que já estava salvo. Isso dá auto-heal: se duas abas colidirem e um OR se
perder, o próximo sync reenvia o acumulado e a cobertura se recompõe — mesmo
espírito da marca d'água de `perc_scrolled`.
"""

BITMAP_SIZE = 100

# Vídeo/podcast considerados concluídos com 90% de cobertura real (espelha o
# MEDIA_COMPLETED_PERC do student_context, que classifica o consumo no perfil).
COVERAGE_COMPLETED_PERC = 90


def normalize_bitmap(value):
    """Sanitiza o bitmap vindo do cliente: exatamente BITMAP_SIZE chars '0'/'1'.

    Retorna None quando não há bitmap utilizável (payload legado ou lixo), para o
    chamador saber que não deve mexer na cobertura."""
    if not isinstance(value, str) or not value:
        return None
    truncated = value[:BITMAP_SIZE]
    normalized = "".join("1" if char == "1" else "0" for char in truncated)
    return normalized.ljust(BITMAP_SIZE, "0")


def merge_bitmap(stored, incoming):
    """OR entre o bitmap salvo e o recebido. Retorna (bitmap, coverage_perc).

    Qualquer um dos lados pode ser None (primeiro acesso / payload legado)."""
    stored_bits = normalize_bitmap(stored)
    incoming_bits = normalize_bitmap(incoming)
    if stored_bits is None and incoming_bits is None:
        return None, 0
    if stored_bits is None:
        merged = incoming_bits
    elif incoming_bits is None:
        merged = stored_bits
    else:
        merged = "".join("1" if a == "1" or b == "1" else "0"
                         for a, b in zip(stored_bits, incoming_bits))
    return merged, merged.count("1")
