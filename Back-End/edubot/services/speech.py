"""Síntese de voz (V.1) — AWS Polly neural + visemas, com cache.

Dá ao EduBot voz de qualidade com lip-sync: `synthesize(text, lang)` devolve o
áudio (mp3) e a timeline de visemas (para a boca do avatar), com CACHE por hash
do texto (intervenções/coach repetem muito → custo tende a centavos).

Degradação graciosa: sem credencial de Polly (a Bedrock API key NÃO cobre Polly),
sem boto3, ou em falha, `synthesize` devolve None e a rota responde
`available:false` — o front cai no Web Speech (comportamento atual). Nada quebra.
"""
import hashlib
import json
import logging
import os

logger = logging.getLogger("edubot.speech")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
VOICES = {
    "pt": os.getenv("EDUBOT_POLLY_VOICE_PT", "Camila"),
    "en": os.getenv("EDUBOT_POLLY_VOICE_EN", "Joanna"),
}
# AV.4 (Plano 3): voz própria por persona (todas neurais do Polly). Antes o
# Einstein falava com a voz "Camila"; agora cada companheiro soa distinto. Persona
# desconhecida (ou 'edubot') cai nas VOICES padrão.
PERSONA_VOICE = {
    "einstein": {"pt": "Thiago", "en": "Matthew"},
    "curie": {"pt": "Vitoria", "en": "Danielle"},
}
CACHE_DIR = os.getenv("EDUBOT_SPEECH_CACHE_DIR", "./speech_cache")
MAX_CHARS = 2900  # limite do Polly neural (3000) com folga
# Liga/desliga a síntese real. "auto" tenta o Polly; "off" força o fallback.
ENABLED = os.getenv("EDUBOT_SPEECH", "auto").lower() != "off"

_polly = None
_unavailable = False  # memoiza a indisponibilidade (não retenta a cada request)


def _cache_paths(key):
    return os.path.join(CACHE_DIR, f"{key}.mp3"), os.path.join(CACHE_DIR, f"{key}.json")


def _key(text, lang):
    return hashlib.sha256(f"{lang}|{text}".encode("utf-8")).hexdigest()


def _get_polly():
    global _polly
    if _polly is None:
        import boto3  # lazy — só quando a síntese é de fato usada
        _polly = boto3.client("polly", region_name=AWS_REGION)
    return _polly


def is_available():
    """True se a síntese real está habilitada e ainda não falhou irremediavelmente."""
    return ENABLED and not _unavailable


def _parse_visemes(marks_text):
    """Polly devolve os speech marks como JSON por linha; extrai a timeline."""
    visemes = []
    for line in marks_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("type") == "viseme" or "value" in j:
            visemes.append({"time_ms": j.get("time", 0), "viseme": j.get("value", "sil")})
    return visemes


def _voice_for(lang, persona):
    """Resolve a voz do Polly: persona conhecida usa a sua; senão, a voz padrão."""
    pv = PERSONA_VOICE.get((persona or "").lower())
    if pv and pv.get(lang):
        return pv[lang]
    return VOICES.get(lang, VOICES["pt"])


def synthesize(text, lang="pt", persona=None):
    """Devolve {key, visemes, cached} ou None (indisponível → o front usa fallback).

    `persona` (AV.4) escolhe a voz; a voz entra na chave do cache, então personas
    diferentes geram áudios diferentes sem colidir. O mp3 é gravado no cache e
    servido por GET /edubot/speech/<key>.mp3."""
    global _unavailable
    if not is_available():
        return None
    text = (text or "").strip()
    if not text:
        return None
    text = text[:MAX_CHARS]
    lang = "en" if lang == "en" else "pt"
    voice = _voice_for(lang, persona)
    key = _key(f"{voice}|{text}", lang)
    mp3_path, vis_path = _cache_paths(key)

    # Cache hit: já sintetizado antes.
    if os.path.exists(mp3_path) and os.path.exists(vis_path):
        with open(vis_path, encoding="utf-8") as fh:
            return {"key": key, "visemes": json.load(fh), "cached": True}

    try:
        polly = _get_polly()
        audio = polly.synthesize_speech(Text=text, VoiceId=voice,
                                        Engine="neural", OutputFormat="mp3")
        audio_bytes = audio["AudioStream"].read()
        marks = polly.synthesize_speech(Text=text, VoiceId=voice, Engine="neural",
                                        OutputFormat="json", SpeechMarkTypes=["viseme"])
        visemes = _parse_visemes(marks["AudioStream"].read().decode("utf-8"))
    except Exception as err:  # noqa: BLE001 — degrada para o fallback
        logger.warning("Polly indisponível (%s); voz cairá no fallback (Web Speech).", err)
        _unavailable = True
        return None

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(mp3_path, "wb") as fh:
        fh.write(audio_bytes)
    with open(vis_path, "w", encoding="utf-8") as fh:
        json.dump(visemes, fh)
    return {"key": key, "visemes": visemes, "cached": False}


def cached_mp3_path(key):
    """Caminho do mp3 em cache para uma key (ou None se não existe). A key é um
    hash sha256 — valida o formato para evitar path traversal."""
    if not key or not all(c in "0123456789abcdef" for c in key) or len(key) != 64:
        return None
    mp3_path, _ = _cache_paths(key)
    return mp3_path if os.path.exists(mp3_path) else None
