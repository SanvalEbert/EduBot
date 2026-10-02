"""Redator de intervenção por caso (B.4).

Hoje o gatilho por evento aplica uma regra e usa um TEMPLATE fixo. Aqui a regra
continua decidindo **se e o quê** (grátis, determinístico); o Haiku redige o
**como** (barato) usando o contexto concreto do aluno — inclusive as últimas
perguntas que ele fez ao tutor (D.1), que é o que mata o texto "genérico". O
template é sempre o fallback (LLM off, sem orçamento, sem consentimento ou falha).

Mesmo padrão de custo do coach (`coach.py`): modelo barato, poucos tokens, system
fixo (cacheável). Nunca levanta — devolve None e o chamador usa o template.
"""
import json
import logging
import os

from edubot.agent import llm

logger = logging.getLogger("edubot.redactor")

# Modelo do redator. Sem EDUBOT_REDACTOR_MODEL, herda o do coach: os dois são o
# mesmo papel de "Haiku barato" e, na Bedrock, o id precisa ser o de INFERENCE
# PROFILE (us....-v1:0) — herdar evita o par desalinhado em que o coach funciona
# e o redator falha com 400 (e ainda alimenta o circuit breaker).
REDACTOR_MODEL = (os.getenv("EDUBOT_REDACTOR_MODEL")
                  or os.getenv("EDUBOT_COACH_MODEL")
                  or "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("EDUBOT_REDACTOR_MAX_TOKENS", "250"))

# System fixo e estável -> bom candidato a prompt caching (cache_control abaixo).
_SYSTEM = (
    "Você é o EduBot, um tutor virtual acolhedor de uma plataforma educacional "
    "brasileira. Reescreva a mensagem de uma intervenção pedagógica para ESTE "
    "aluno específico, em 2 a 3 frases curtas, calorosas e diretas (sem listas, "
    "sem markdown, sem emojis). Use o primeiro nome e, se houver, cite a dúvida "
    "que ele levou ao tutor e a competência mais frágil — seja concreto, não "
    "genérico. Mantenha o mesmo OBJETIVO pedagógico da regra disparada. Se o "
    "campo 'formato_preferido' vier preenchido, PROPONHA no formato em que o "
    "aluno mais aprende (ex.: 'preparei um vídeo curto...'). Se o campo "
    "'historico_outcomes' indicar que intervenções recentes foram DISPENSADAS, "
    "VARIE a abordagem (outro ângulo, outro tom, outro formato) em vez de "
    "repetir o que não funcionou. Responda apenas com o texto final, no idioma "
    "pedido."
)


def redigir_intervencao(digest, rec, lang="pt"):
    """Devolve o texto redigido pela LLM, ou None (usar o template rec['mensagem_aluno']).

    `digest` já vem minimizado (primeiro nome, sem RA). `rec` é a recomendação da
    regra (tipo, prioridade, mensagem_aluno template, justificativa)."""
    if not llm.is_real():
        return None
    idioma = "inglês" if lang == "en" else "português do Brasil"
    payload = {
        "idioma": idioma,
        "regra": rec.get("tipo"),
        "objetivo_template": rec.get("mensagem_aluno"),
        **digest,
    }
    user = (
        "Contexto do aluno e da regra (JSON):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nReescreva a mensagem da intervenção para este aluno."
    )
    try:
        resp = llm.messages_create(
            system=[{"type": "text", "text": _SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            max_tokens=MAX_TOKENS,
            model=REDACTOR_MODEL,
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or None
    except Exception as err:  # noqa: BLE001 — degrada para o template
        logger.warning("Redator LLM indisponível (%s); usando template.", err)
        return None
