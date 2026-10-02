# V.1 — Rotas de voz do EduBot (AWS Polly neural + visemas).
#
#   POST /edubot/speak            body: {text, lang}
#     -> {available, audio_url, visemes:[{time_ms, viseme}], cached}
#        available:false quando a síntese real não está disponível (o front
#        cai no Web Speech). O aluno vem do token (@require_auth).
#   GET  /edubot/speech/<key>.mp3 -> serve o mp3 em cache (key = hash sha256,
#        não sensível: é a voz do BOT). Sem auth para o <audio> do navegador
#        conseguir tocar (o <audio src> não manda header Authorization).
from flask import Blueprint, request, send_file
from flask_cors import cross_origin
import json

from edubot.api.auth import require_auth
from edubot.api.http import get_payload
from edubot.services import speech

app_speech = Blueprint("speech", __name__)


@app_speech.route("/edubot/speak", methods=["POST"])
@cross_origin()
@require_auth
def speak():
    data = get_payload()
    text = data.get("text") or ""
    lang = "en" if data.get("lang") == "en" else "pt"
    # AV.4: persona opcional escolhe a voz (Einstein/Curie têm voz própria).
    persona = data.get("persona")
    result = speech.synthesize(text, lang, persona=persona)
    if result is None:
        # Degradação graciosa: o front usa o Web Speech.
        return json.dumps({"available": False}), 200
    return json.dumps({
        "available": True,
        "audio_url": f"/edubot/speech/{result['key']}.mp3",
        "visemes": result["visemes"],
        "cached": result["cached"],
    }), 200


@app_speech.route("/edubot/speech/<key>.mp3", methods=["GET"])
@cross_origin()
def speech_mp3(key):
    path = speech.cached_mp3_path(key)
    if path is None:
        return json.dumps({"Error": "Áudio não encontrado"}), 404
    resp = send_file(path, mimetype="audio/mpeg", conditional=True)
    # Cache no navegador: a voz de um mesmo texto não muda.
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp
