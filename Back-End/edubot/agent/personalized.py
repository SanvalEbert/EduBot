# MELHORIA (OVA personalizada) — Agente EduBot com tool-use.
#
# Ao contrário de get_recommendation (uma chamada só, em agent.py), aqui o
# EduBot é um AGENTE: ele decide, em vários passos, quais tools chamar para
# diagnosticar o assunto fraco do aluno, buscar conteúdo no banco e montar uma
# OVA de reforço.
#
# O LOOP de tool-use abaixo é REAL e definitivo — é exatamente o que roda com o
# Claude via Bedrock/Anthropic. O que está mockado é só o "cérebro": o
# _MockAgentClient devolve o MESMO envelope de tool-use da Anthropic Messages
# API (blocos tool_use, stop_reason "tool_use") tomando decisões determinísticas
# a partir do estado da conversa. Ligar a LLM real = trocar _client por um
# cliente boto3/anthropic (esqueleto comentado no fim). Nada mais muda.
import json
import uuid

from . import llm
from .tools import TOOLS_SCHEMA, execute_tool

BEDROCK_MODEL_ID = "anthropic.claude-sonnet-4-5-20250929-v1:0"

# Teto de iterações do loop (guarda contra loop infinito de tool-use).
MAX_ITERATIONS = 8


SYSTEM_PROMPT = """Você é o EduBot, um agente pedagógico de uma plataforma educacional \
brasileira. Sua tarefa é montar UMA "OVA personalizada" de reforço para o aluno: uma \
trilha curta de conteúdo focada na competência (assunto) em que ele foi pior.

Use as ferramentas disponíveis, nesta ordem:
1. listar_competencias_fracas — identifique a competência mais fraca do aluno.
2. listar_recursos_remediacao — para essa competência, busque vídeos e textos de reforço.
3. listar_questoes_reforco — busque questões dessa competência para fixar o conteúdo.
4. criar_ova_personalizada — monte a OVA com os recursos e questões escolhidos, uma \
mensagem motivacional dirigida ao aluno pelo primeiro nome, e uma justificativa para o \
professor. Chame esta ferramenta uma única vez, ao final.

Selecione conteúdo SOMENTE da competência-alvo. COMECE a trilha pelo formato em que o \
aluno mais aprende — o campo `formato_preferido_do_aluno` de listar_recursos_remediacao \
indica esse formato (vídeo/texto/podcast); coloque esse recurso primeiro. Se não houver \
material nesse formato, use o que houver (não deixe a trilha vazia). Depois de criar a \
OVA, responda com uma frase curta de confirmação."""


USER_PROMPT_TEMPLATE = """Gere a OVA personalizada de reforço para este aluno, seguindo \
o processo do sistema.

PERFIL DO ALUNO (JSON):
{profile_json}"""


def _build_user_prompt(profile):
    return USER_PROMPT_TEMPLATE.format(
        profile_json=json.dumps(profile, ensure_ascii=False, indent=2, default=str))


# ---------------------------------------------------------------------------
# Envelopes no formato da Anthropic Messages API (iguais aos do Bedrock)
# ---------------------------------------------------------------------------
def _tool_use_envelope(name, tool_input):
    return {
        "id": f"msg_{uuid.uuid4().hex[:12]}",
        "type": "message",
        "role": "assistant",
        "model": BEDROCK_MODEL_ID,
        "stop_reason": "tool_use",
        "content": [{
            "type": "tool_use",
            "id": f"toolu_{uuid.uuid4().hex[:12]}",
            "name": name,
            "input": tool_input,
        }],
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


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


def _collect_results(messages):
    """Reconstrói, a partir do histórico, o resultado (parseado) de cada tool já
    executada — é o que o mock usa para decidir o próximo passo."""
    id_to_name = {}
    results = {}
    for m in messages:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if b.get("type") == "tool_use":
                id_to_name[b["id"]] = b["name"]
            elif b.get("type") == "tool_result":
                name = id_to_name.get(b.get("tool_use_id"))
                if name:
                    try:
                        results[name] = json.loads(b["content"])
                    except (ValueError, TypeError, KeyError):
                        results[name] = b.get("content")
    return results


def _pick_target(comps, profile, forced_competency_id):
    """Competência que a trilha vai remediar.

    Sem alvo explícito, mantém o comportamento histórico (a primeira da lista de
    fracas, que já vem ordenada). Com alvo explícito, usa-o — buscando o nome no
    perfil quando a competência não estiver entre as "fracas" (é o caso de um
    gatilho pós-quiz numa competência que só agora começou a cair)."""
    if forced_competency_id is None:
        return comps[0] if comps else None
    for comp in comps:
        if comp.get("competency_id") == forced_competency_id:
            return comp
    for comp in profile.get("competencias", []):
        if comp.get("competency_id") == forced_competency_id:
            return comp
    return comps[0] if comps else None


# ---------------------------------------------------------------------------
# Cliente mockado: simula o Claude escolhendo as tools, de forma determinística.
# ---------------------------------------------------------------------------
class _MockAgentClient:
    def invoke(self, system, messages, tools, ctx):
        profile = ctx.get("profile", {})
        done = _collect_results(messages)

        if "listar_competencias_fracas" not in done:
            return _tool_use_envelope("listar_competencias_fracas", {})

        comps = (done.get("listar_competencias_fracas") or {}).get("competencias", [])
        # Fase 4 do Plano de Rastreabilidade: quando o gatilho já sabe QUAL
        # competência remediar (o aluno acabou de errar aquele assunto), o alvo
        # vem explícito e o diagnóstico não escolhe por conta própria. Sem isso,
        # concluir o OVA X com dificuldade podia gerar reforço do OVA Y — a
        # competência mais fraca GLOBAL —, o que confunde o aluno.
        target = _pick_target(comps, profile, ctx.get("target_competency_id"))
        comp_id = target["competency_id"] if target else None

        if "listar_recursos_remediacao" not in done:
            return _tool_use_envelope("listar_recursos_remediacao", {"competency_id": comp_id})

        if "listar_questoes_reforco" not in done:
            return _tool_use_envelope("listar_questoes_reforco", {"competency_id": comp_id})

        if "criar_ova_personalizada" not in done:
            recursos = (done.get("listar_recursos_remediacao") or {}).get("recursos", [])
            questoes = (done.get("listar_questoes_reforco") or {}).get("questoes", [])
            nome = (profile.get("estudante", {}) or {}).get("nome") or "estudante"
            primeiro = nome.split()[0]
            comp_nome = target["nome"] if target else "este assunto"
            taxa = target.get("taxa_erro") if target else None
            mensagem = (
                f"{primeiro}, preparei uma trilha de reforço sobre \"{comp_nome}\", "
                "onde percebi mais dificuldade. Comece pelos vídeos e textos e, ao "
                "final, refaça as questões para consolidar o aprendizado.")
            justificativa = (
                f"Competência \"{comp_nome}\" (id {comp_id}) com status "
                f"'{target.get('status') if target else 'desconhecido'}'"
                + (f" e taxa de erro {taxa} no quiz." if taxa is not None else "."))
            return _tool_use_envelope("criar_ova_personalizada", {
                "target_competency_id": comp_id,
                "titulo": f"Reforço: {comp_nome}",
                "mensagem_aluno": mensagem,
                "justificativa": justificativa,
                "resource_ids": [r["resource_id"] for r in recursos],
                "question_ids": [q["question_id"] for q in questoes],
            })

        created = done.get("criar_ova_personalizada") or {}
        if created.get("personalized_ova_id"):
            text = (
                f"Pronto! Criei a OVA de reforço (id {created['personalized_ova_id']}) "
                f"com {created.get('itens_recursos', 0)} recurso(s) e "
                f"{created.get('itens_questoes', 0)} questão(ões).")
        else:
            text = ("Não encontrei conteúdo de reforço suficiente para montar a OVA "
                    "personalizada deste aluno.")
        return _text_envelope(text)


# B.3: o loop de tool-use foi extraído para agent/loop.py (genérico, reutilizado
# por outros fluxos do agente). Aqui só permanece o que é ESPECÍFICO da OVA
# personalizada: o system prompt, o mock determinístico e o mapeamento do
# resultado. O comportamento (e o teste de regressão) é idêntico.
def run_personalized_ova_agent(student, profile, target_competency_id=None):
    """Roda o agente de tool-use e devolve o resultado da geração.

    student: linha Students (g.student) — usada pelas tools como contexto seguro.
    profile: dict de build_student_profile (entrada do agente).
    target_competency_id: competência a remediar (Fase 4). None mantém o
        diagnóstico automático (a mais fraca), que é o comportamento histórico.
    """
    from .loop import run_agent

    est = profile.get("estudante", {}) or {}
    fracas = profile.get("competencias", [])
    digest = {
        "primeiro_nome": (est.get("nome") or "").split(" ")[0],
        "competencia_alvo": (min(fracas, key=lambda c: c.get("dominio_estimado")
                                 if c.get("dominio_estimado") is not None else 1.0)
                             ["nome"] if fracas else None),
        "competencia_forcada": target_competency_id,
    }

    result = run_agent(
        SYSTEM_PROMPT, _build_user_prompt(profile), TOOLS_SCHEMA,
        ctx={"student": student, "profile": profile,
             "target_competency_id": target_competency_id},
        model=None, max_iterations=MAX_ITERATIONS,
        trigger_type="personalized_ova",
        mock_client=_MockAgentClient(),
        input_digest=digest)

    created = result["results_by_tool"].get("criar_ova_personalizada")
    if isinstance(created, dict) and not created.get("personalized_ova_id"):
        created = None

    # P.2 — formato pelo qual a trilha foi montada (para o front mostrar o chip
    # "no seu formato"); vem da tool de recursos (mesma fonte que o agente usou).
    recursos_tool = result["results_by_tool"].get("listar_recursos_remediacao") or {}
    formato_preferido = recursos_tool.get("formato_preferido_do_aluno") \
        if isinstance(recursos_tool, dict) else None

    return {
        "personalized_ova_id": created["personalized_ova_id"] if created else None,
        "resultado": created,
        "mensagem_final": result["final_text"],
        "iteracoes": result["iterations"],
        "mock": result["mock"],
        "model_id": result["model_id"] or BEDROCK_MODEL_ID,
        "formato_preferido": formato_preferido,
    }


# ---------------------------------------------------------------------------
# Integração futura com a LLM real (NÃO usada hoje). O loop acima já é o
# definitivo — basta um cliente cujo .invoke devolva o envelope da Messages API
# com tools. Exemplo com a API da Anthropic:
#
# import anthropic
# class _AnthropicAgentClient:
#     def __init__(self):
#         self._client = anthropic.Anthropic()  # ANTHROPIC_API_KEY no ambiente
#     def invoke(self, system, messages, tools, profile):
#         resp = self._client.messages.create(
#             model="claude-sonnet-4-5-20250929",
#             max_tokens=1024,
#             system=system,
#             tools=[{"name": t["name"], "description": t["description"],
#                     "input_schema": t["input_schema"]} for t in tools],
#             messages=messages,
#         )
#         return resp.model_dump()   # mesmo formato (content[], stop_reason)
#
# _client = _AnthropicAgentClient()
#
# Para AWS Bedrock, usar bedrock-runtime.converse(...) com toolConfig e adaptar
# a resposta (já vem em content/stop_reason equivalentes).
# ---------------------------------------------------------------------------
