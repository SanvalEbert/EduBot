"""i18n de conteúdo (Fase 4 — A12).

O conteúdo semeado tem colunas de tradução (`*_en`) no banco; este helper
resolve o valor no idioma pedido com degradação segura: sem tradução, cai no
PT original. Vive fora da camada HTTP para os serviços (student_context,
proactivity) usarem sem depender de Flask.
"""

SUPPORTED_LANGS = ("pt", "en")


def norm_lang(lang):
    """Normaliza o idioma para 'pt' | 'en' (default 'pt')."""
    lang = (lang or "pt").lower()
    return lang if lang in SUPPORTED_LANGS else "pt"


def tr(pt_value, en_value, lang):
    """Valor no idioma pedido; EN vazio/nulo degrada para o PT."""
    if norm_lang(lang) == "en" and en_value:
        return en_value
    return pt_value
