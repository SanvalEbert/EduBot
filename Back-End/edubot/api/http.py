"""Utilitários HTTP compartilhados pelas rotas.

`get_payload` centraliza a leitura do corpo JSON e mata o envelope `[data]`
(A16): a convenção antiga obrigava todo POST a mandar um array de um elemento
(`[obj]`), herança do front jQuery, gerando IndexError não tratado quando o
corpo vinha diferente. Agora o contrato é o objeto puro; durante a transição
(o legado só é aposentado na Fase 5) ainda aceitamos o envelope `[obj]`.
"""
from flask import abort, request

from edubot.i18n import norm_lang


def get_lang():
    """Idioma pedido pela requisição (?lang=en), normalizado para pt|en.

    Fase 4 (A12): o conteúdo do banco tem colunas de tradução e as rotas de
    conteúdo servem o idioma pedido, com fallback PT."""
    return norm_lang(request.args.get("lang"))


def get_payload():
    """Retorna o corpo JSON da requisição como dict.

    Aceita tanto o objeto puro (contrato novo) quanto o envelope legado `[obj]`.
    Aborta com 400 (JSON, via error handler global) se o corpo for inválido."""
    data = request.get_json(silent=True)
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        abort(400, description="Corpo da requisição inválido (esperado objeto JSON).")
    return data
