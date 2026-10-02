# MELHORIA (Tutor IA por OVA) — Chat de tutoria restrito ao conteúdo do OVA.
#
# Diferente de get_recommendation (agent.py) e do agente de tool-use
# (personalized.py), aqui o EduBot atua como um TUTOR conversacional: o aluno
# faz perguntas e o tutor responde ESTRITAMENTE com base no conteúdo do OVA que
# ele acabou de consumir (grounding).
#
# Seguindo a convenção do projeto, o "cérebro" (a LLM) está MOCKADO: o
# _MockTutorClient devolve o MESMO envelope da Anthropic Messages API
# (content[].text, stop_reason) que o Bedrock/Anthropic devolveria. Ligar a LLM
# real = trocar _client por um cliente boto3/anthropic (esqueleto comentado no
# fim do arquivo). O prompt, o parsing e a rota já são os definitivos.
#
# O grounding é feito por uma recuperação determinística (overlap de palavras-
# chave) sobre o contexto do OVA. Quando a LLM real entrar, o MESMO contexto vai
# no system prompt — o tutor real fica preso ao material do mesmo jeito.
import re
import unicodedata
import uuid

from . import llm
from .persona import style_prompt, bordao

BEDROCK_MODEL_ID = "anthropic.claude-sonnet-4-5-20250929-v1:0"

# Quantos trechos do material citar na resposta.
MAX_PASSAGES = 2
# Tamanho máximo do contexto aceito (proteção contra payloads gigantes).
MAX_CONTEXT_CHARS = 20000


SYSTEM_PROMPT_TEMPLATE = """Você é o EduBot Tutor, um tutor pedagógico da plataforma \
educacional. Você está ajudando o aluno a tirar dúvidas sobre UM objeto virtual de \
aprendizagem (OVA) específico, intitulado "{titulo}".

REGRAS:
- Responda SOMENTE com base no material do OVA fornecido abaixo. Não invente fatos que \
não estejam no material.
- Se a pergunta não tiver relação com o conteúdo do OVA, diga educadamente que ela está \
fora do escopo deste material e sugira tópicos do OVA que você PODE responder.
- Seja claro, didático e direto. Responda em {idioma}.

MATERIAL DO OVA:
{contexto}"""


# ---------------------------------------------------------------------------
# Utilitários de texto (normalização e recuperação determinística)
# ---------------------------------------------------------------------------
_STOPWORDS = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
    "das", "e", "ou", "que", "qual", "quais", "quando", "como", "onde", "por",
    "para", "com", "sem", "em", "no", "na", "nos", "nas", "ao", "aos", "se",
    "sua", "seu", "suas", "seus", "este", "esta", "isso", "essa", "esse", "é",
    "são", "ser", "the", "of", "to", "and", "me", "explica", "explique", "sobre",
    "fale", "diga", "pode", "poderia", "quero", "saber", "entender", "significa",
    "qual", "porque", "porquê", "mais", "menos", "muito", "tem", "há", "dá",
}


def _strip_accents(text):
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn")


def _keywords(text):
    words = re.findall(r"[a-zA-Z0-9áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]+", text.lower())
    out = set()
    for w in words:
        w = _strip_accents(w)
        if len(w) >= 3 and w not in _STOPWORDS:
            out.add(w)
    return out


def _parse_context(context):
    """Quebra o contexto do OVA em (heading, passagem). O frontend envia o
    material no formato:
        ## <título da seção>
        <parágrafo>
        <parágrafo>
        ## <título da seção>
        ...
    Cada parágrafo vira uma passagem associada à sua seção."""
    passages = []
    headings = []
    current = "Introdução"
    for raw in (context or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            if current:
                headings.append(current)
        elif line.startswith("# "):
            continue  # título geral do OVA — ignorado aqui
        else:
            passages.append({"heading": current, "text": line})
    return passages, headings


def _score(question_kw, passage):
    pk = _keywords(passage["text"]) | _keywords(passage["heading"])
    if not pk:
        return 0
    return len(question_kw & pk)


def _retrieve(question, passages):
    qk = _keywords(question)
    if not qk:
        return []
    ranked = sorted(
        ((_score(qk, p), i, p) for i, p in enumerate(passages)),
        key=lambda t: (-t[0], t[1]))
    return [p for score, _, p in ranked if score > 0][:MAX_PASSAGES]


# ---------------------------------------------------------------------------
# Cliente mockado: simula o Claude tutor de forma determinística.
# ---------------------------------------------------------------------------
class _MockTutorClient:
    def invoke(self, system, messages, titulo, passages, headings, lang="pt", persona=None):
        # Fase 4 (A12): o mock também responde no idioma do aluno.
        def T(pt, en):
            return en if lang == "en" else pt

        question = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                question = m.get("content", "")
                break

        # CP.4: bordão determinístico da persona (perceptível sem LLM real).
        pre = bordao(persona, seed=len(question), lang=lang)

        relevant = _retrieve(question, passages)

        if not relevant:
            sugeridos = headings[:3]
            dicas = ("; ".join(sugeridos)) if sugeridos else T(
                "os tópicos apresentados", "the topics presented")
            text = T(
                f"Essa pergunta parece fora do conteúdo deste OVA (\"{titulo}\"). "
                f"Como tutor deste material, posso te ajudar com temas como: {dicas}. "
                "Sobre o que desse conteúdo você gostaria de saber mais?",
                f"That question seems outside the content of this OVA (\"{titulo}\"). "
                f"As the tutor for this material, I can help you with topics such as: {dicas}. "
                "What would you like to know more about from this content?")
            return _text_envelope(pre + text)

        citacoes = " ".join(f"\"{p['text']}\"" for p in relevant)
        secao = relevant[0]["heading"]
        text = T(
            f"Boa pergunta! No material deste OVA, na parte sobre \"{secao}\", "
            f"o conteúdo aponta que: {citacoes} "
            "Se quiser, posso aprofundar esse ponto ou relacioná-lo com outro tópico do OVA.",
            f"Good question! In this OVA's material, in the section about \"{secao}\", "
            f"the content states that: {citacoes} "
            "If you'd like, I can go deeper into this point or relate it to another topic in the OVA.")
        return _text_envelope(pre + text)


def _text_envelope(text):
    return {
        "id": f"msg_{uuid.uuid4().hex[:12]}",
        "type": "message",
        "role": "assistant",
        "model": BEDROCK_MODEL_ID,
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


_client = _MockTutorClient()


def tutor_reply(titulo, context, messages, lang="pt", persona=None):
    """Ponto de entrada do tutor: título + material do OVA + histórico de chat
    -> resposta do tutor (texto).

    titulo: nome do OVA.
    context: material do OVA (texto extraído do conteúdo que o aluno consumiu).
    messages: [{"role": "user"|"assistant", "content": str}, ...]
    lang: idioma da resposta (Fase 4 — A12), no mock e na LLM real.
    persona: CP.4 — muda só o TOM (estilo do personagem); grounding inalterado.
    """
    context = (context or "")[:MAX_CONTEXT_CHARS]
    passages, headings = _parse_context(context)
    system = SYSTEM_PROMPT_TEMPLATE.format(
        titulo=titulo or ("this OVA" if lang == "en" else "este OVA"),
        contexto=context,
        idioma="inglês" if lang == "en" else "português do Brasil")
    # CP.4: parágrafo de estilo da persona no system prompt (tom, não regras).
    estilo = style_prompt(persona, lang)
    if estilo:
        system = f"{system}\n\n{estilo}"

    # Referenciação automática (Cena 2): identifica de quais seções do material a
    # resposta foi ancorada, para o frontend exibir "Fonte: <seção>".
    last_question = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_question = m.get("content", "")
            break
    sources = [
        {"secao": p["heading"], "trecho": p["text"][:160]}
        for p in _retrieve(last_question, passages)
    ]

    # Caminho REAL (Bedrock/Anthropic) quando configurado por ambiente. O
    # MATERIAL DO OVA já está no system prompt, então o tutor real responde
    # preso ao conteúdo do mesmo jeito que o mock. Se a chamada falhar
    # (credencial/rede), cai no mock para o chat não quebrar.
    if llm.is_real():
        try:
            resp = llm.messages_create(
                system=system,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            )
            reply = "".join(b.text for b in resp.content if b.type == "text")
            usage = getattr(resp, "usage", None)
            # B.2: a rota registra a decisão (metadados + tokens) — o tutor-chat
            # é chamada REAL paga e precisa contar no orçamento diário.
            return {"reply": reply, "model_id": resp.model, "mock": False,
                    "sources": sources,
                    "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                    "output_tokens": getattr(usage, "output_tokens", 0) or 0}
        except Exception as err:  # noqa: BLE001 — degrada graciosamente para o mock
            print(f"[tutor] LLM real falhou ({err}); usando mock.")

    response = _client.invoke(
        system=system, messages=messages,
        titulo=titulo or ("this OVA" if lang == "en" else "este OVA"),
        passages=passages, headings=headings, lang=lang, persona=persona)

    reply = "".join(b.get("text", "") for b in response.get("content", [])
                    if b.get("type") == "text")
    return {
        "reply": reply,
        "model_id": response.get("model", BEDROCK_MODEL_ID),
        "mock": isinstance(_client, _MockTutorClient),
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# Integração futura com a LLM real (NÃO usada hoje). O contrato de tutor_reply
# não muda — basta um cliente cujo .invoke devolva o envelope da Messages API.
#
# import anthropic
# class _AnthropicTutorClient:
#     def __init__(self):
#         self._client = anthropic.Anthropic()  # ANTHROPIC_API_KEY no ambiente
#     def invoke(self, system, messages, titulo, passages, headings):
#         resp = self._client.messages.create(
#             model="claude-sonnet-4-6",
#             max_tokens=1024,
#             system=system,  # já contém o MATERIAL DO OVA (grounding)
#             messages=[{"role": m["role"], "content": m["content"]} for m in messages],
#         )
#         return resp.model_dump()  # mesmo formato (content[], stop_reason)
#
# _client = _AnthropicTutorClient()
#
# Para AWS Bedrock, usar bedrock-runtime.converse(...) com o system contendo o
# material do OVA; a resposta já vem em content/stop_reason equivalentes.
# ---------------------------------------------------------------------------
