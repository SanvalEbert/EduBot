"""CP.4 (Plano 3) — ESTILO de fala por persona do companheiro de estudo.

O aluno escolhe um personagem (edubot | einstein | curie) e ele passa a "falar"
tanto no chat do tutor (tutor.py) quanto no coach de desempenho (coach.py). Este
módulo concentra:

  - `style_prompt(persona, lang)`: um parágrafo de ESTILO que entra no system
    prompt da LLM real — muda o TOM, nunca as regras de grounding (o tutor continua
    preso ao material do OVA);
  - `bordao(persona, seed)`: um prefixo determinístico (2 variações) para o cliente
    MOCK, de modo que a persona seja perceptível e TESTÁVEL mesmo sem LLM real.

`edubot` (mascote) é o tom neutro atual: sem estilo extra, sem bordão.
Persona desconhecida cai em `edubot` (degradação silenciosa).
"""

VALID_STYLE_PERSONAS = ("einstein", "curie")


def normalize_persona(persona):
    """Retorna a persona se ela tem estilo próprio; senão None (tom neutro)."""
    p = (persona or "").strip().lower()
    return p if p in VALID_STYLE_PERSONAS else None


# Parágrafo de estilo por persona/idioma (entra no system prompt da LLM real).
_STYLE = {
    "einstein": {
        "pt": ("ESTILO: incorpore o Prof. Einstein — explique com ANALOGIAS do "
               "cotidiano e da física (\"imagine um trem em movimento...\", \"é como "
               "se...\"), com tom curioso e encantado pela descoberta. Faça o aluno "
               "IMAGINAR. Isso muda apenas o seu tom; continue respondendo SOMENTE "
               "com base no material do OVA."),
        "en": ("STYLE: embody Prof. Einstein — explain with everyday, physical "
               "ANALOGIES (\"imagine a moving train...\", \"it's as if...\"), with a "
               "curious tone delighted by discovery. Make the student IMAGINE. This "
               "changes only your tone; keep answering ONLY from the OVA material."),
    },
    "curie": {
        "pt": ("ESTILO: incorpore a Dra. Marie Curie — seja METÓDICA e paciente, "
               "explique POR ETAPAS como num experimento de laboratório (\"vamos por "
               "partes...\", \"observe o que acontece quando...\"), valorizando a "
               "perseverança. Isso muda apenas o seu tom; continue respondendo "
               "SOMENTE com base no material do OVA."),
        "en": ("STYLE: embody Dr. Marie Curie — be METHODICAL and patient, explain "
               "STEP BY STEP as in a lab experiment (\"let's go part by part...\", "
               "\"observe what happens when...\"), valuing perseverance. This changes "
               "only your tone; keep answering ONLY from the OVA material."),
    },
}

# Bordões do MOCK (2 variações determinísticas por persona/idioma).
_BORDAO = {
    "einstein": {
        "pt": ["Imagine só: ", "Pensando como um físico curioso, "],
        "en": ["Just imagine: ", "Thinking like a curious physicist, "],
    },
    "curie": {
        "pt": ["Vamos por partes, como num laboratório. ", "Com método e paciência: "],
        "en": ["Let's go part by part, like in a lab. ", "With method and patience: "],
    },
}


def style_prompt(persona, lang="pt"):
    """Parágrafo de estilo para o system prompt (string vazia = tom neutro)."""
    p = normalize_persona(persona)
    if not p:
        return ""
    lang = "en" if lang == "en" else "pt"
    return _STYLE[p][lang]


def bordao(persona, seed=0, lang="pt"):
    """Prefixo determinístico do mock (string vazia = sem bordão). `seed` escolhe
    entre as 2 variações (ex.: len da pergunta) — estável entre execuções."""
    p = normalize_persona(persona)
    if not p:
        return ""
    lang = "en" if lang == "en" else "pt"
    opts = _BORDAO[p][lang]
    return opts[abs(int(seed)) % len(opts)]
