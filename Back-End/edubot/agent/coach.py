# MELHORIA (Roteiro Cena 3) — Mensagem falada do EduBot ("coach") gerada por IA.
#
# Gera um texto CURTO e HUMANO sobre o progresso do aluno, para o personagem
# virtualizado falar. Fase 3d: passou a usar a MESMA camada de provider
# (edubot.agent.llm) dos outros agentes — antes tinha um caminho boto3
# invoke_model paralelo. Continua SOB DEMANDA, com modelo barato (override) e
# poucos tokens para controlar custo. Sem provider real configurado (ou em
# falha), devolve None e o frontend usa o texto determinístico local.
import json
import os

from edubot.agent import llm

# Modelo barato (override do modelo padrão do provider) — controle de custo.
COACH_MODEL = os.getenv("EDUBOT_COACH_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("EDUBOT_COACH_MAX_TOKENS", "220"))


def _profile_digest(profile):
    """Resumo compacto do perfil (poucos tokens de entrada = menos custo)."""
    comp = profile.get("competencias", [])
    desenvolvidas = [c["nome"] for c in comp if c.get("status") == "desenvolvida"]
    fracas = sorted(
        [c for c in comp if (c.get("taxa_erro") or 0) > 0.5],
        key=lambda c: -(c.get("taxa_erro") or 0))
    return {
        "nome": (profile.get("estudante", {}) or {}).get("nome"),
        "percentual_consumido": profile.get("recursos", {}).get("percentual_consumido"),
        "dias_sem_acesso": profile.get("dias_sem_acesso"),
        "taxa_erro_quiz": profile.get("quiz", {}).get("taxa_erro"),
        "competencias_desenvolvidas": desenvolvidas,
        "competencia_mais_fraca": fracas[0]["nome"] if fracas else None,
    }


_SYSTEM = (
    "Você é o EduBot, um tutor virtual simpático e encorajador de uma plataforma "
    "educacional. Fale DIRETAMENTE com o aluno, em tom caloroso, humano e "
    "motivador — como um mentor que acompanha o progresso dele. Seja específico "
    "usando os dados fornecidos (percentual consumido, competências, dificuldade). "
    "Escreva de 2 a 3 frases curtas, naturais para serem FALADAS em voz alta "
    "(sem listas, sem markdown, sem emojis). Responda no idioma pedido."
)


def coach_message(profile, lang="pt", persona=None):
    """Devolve (texto, model_id) ou None se a IA não estiver disponível.

    D.5: a fala do coach é LLM SOBRE OS DADOS do aluno — exige consentimento
    `ia_sobre_dados`. Sem ele, retorna None (o front usa o texto local
    determinístico), como quando a IA não está configurada.
    persona (CP.4): muda só o TOM da fala (estilo do personagem)."""
    if not llm.is_real():
        return None
    student_id = (profile.get("estudante", {}) or {}).get("student_id")
    if student_id is not None:
        from edubot.services.consents import has_consent
        if not has_consent(student_id, "ia_sobre_dados"):
            return None

    idioma = "inglês" if lang == "en" else "português do Brasil"
    user = (
        f"Idioma da resposta: {idioma}.\n"
        f"Dados do aluno (JSON): {json.dumps(_profile_digest(profile), ensure_ascii=False)}\n"
        "Gere a fala do EduBot sobre o progresso deste aluno."
    )
    # CP.4: estilo da persona anexado ao system (tom; sem mudar o que é dito).
    from edubot.agent.persona import style_prompt
    estilo = style_prompt(persona, lang)
    system = f"{_SYSTEM}\n\n{estilo}" if estilo else _SYSTEM

    try:
        import time
        started = time.time()
        resp = llm.messages_create(
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=MAX_TOKENS,
            model=COACH_MODEL,  # modelo barato só para a fala do coach
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        # B.2 — toda chamada REAL entra na trilha de decisões: sem isto, o gasto
        # do coach (endpoint que o aluno pode chamar à vontade) ficava fora do
        # somatório do orçamento diário (budget_exceeded).
        if text:
            from edubot.services.decisions import record_decision
            usage = getattr(resp, "usage", None)
            record_decision(
                student_id, "coach", model_id=resp.model, mock=False,
                latency_ms=int((time.time() - started) * 1000),
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0)
        return (text, resp.model) if text else None
    except Exception as err:  # noqa: BLE001 — degrada para o texto local
        print(f"[coach] LLM indisponível ({err}); usando texto local.")
        return None
