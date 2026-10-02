"""Loop de tool-use genérico (B.3).

Generaliza o loop que já rodava (e era testado) em `personalized.py`: a percepção
já vem no `user_prompt`; cada `tool_use` do modelo é executado por `execute_tool`
(validação server-side); ao final, a decisão é SEMPRE registrada em
`agent_decisions` (B.2) com custo/latência estimados.

O "cérebro" é injetável: com LLM real (`llm.is_real()`) usa o Claude via
Bedrock/Anthropic; sem ele, o chamador passa um `mock_client` determinístico
(é assim que `personalized.py` mantém o comportamento e o teste de regressão).
Assim o loop (plumbing) é único e o comportamento específico vive nos prompts +
no mock de cada fluxo.
"""
import json
import logging
import time

from . import llm
from .tools import execute_tool
from edubot.services.decisions import record_decision, estimate_cost

logger = logging.getLogger("edubot.agent.loop")


class _RealAgentClient:
    """Cérebro real: Claude via a camada llm.py. Devolve o envelope da Messages
    API (model_dump) que o loop consome — mesmo formato do mock."""
    def __init__(self, model=None, max_tokens=2048):
        self.model = model
        self.max_tokens = max_tokens

    def invoke(self, system, messages, tools, ctx):
        resp = llm.messages_create(
            system=system,
            messages=messages,
            tools=[{"name": t["name"], "description": t["description"],
                    "input_schema": t["input_schema"]} for t in tools],
            max_tokens=self.max_tokens,
            model=self.model,
        )
        return resp.model_dump()


def run_agent(system, user_prompt, tools_schema, ctx, *, model=None,
              max_iterations=8, trigger_type="on_demand", mock_client=None,
              input_digest=None, record=True):
    """Executa o loop de tool-use e devolve um resultado estruturado.

    Retorna dict: final_text, actions (tools de escrita bem-sucedidas),
    results_by_tool (último resultado por tool), tools_called [{name, ok}],
    iterations, input_tokens, output_tokens, mock, model_id, decision_id.

    `ctx` carrega o aluno logado (ctx['student']) — as tools o usam como contexto
    seguro. `mock_client.invoke(system, messages, tools, ctx)` é usado quando não
    há LLM real. Se não houver LLM real nem mock, levanta RuntimeError."""
    real = llm.is_real()
    client = _RealAgentClient(model=model) if real else mock_client
    if client is None:
        raise RuntimeError("run_agent sem LLM real e sem mock_client.")

    messages = [{"role": "user", "content": user_prompt}]
    final_text = ""
    tools_called = []
    actions = []
    results_by_tool = {}
    input_tokens = output_tokens = 0
    iterations = 0
    model_id = None
    started = time.time()

    for _ in range(max_iterations):
        iterations += 1
        try:
            response = client.invoke(system=system, messages=messages,
                                     tools=tools_schema, ctx=ctx)
        except Exception:
            # Degradação graciosa (mesmo padrão de coach/tutor/agent): se o LLM
            # real falha no meio do loop (ex.: token expirado, timeout — o
            # breaker já foi alimentado em llm.messages_create) e há um mock
            # determinístico, cai nele em vez de estourar 500 na rota. O flag
            # `real` vira False -> a decisão é registrada como mock e o custo, 0.
            if mock_client is None or not real:
                raise
            logger.warning("LLM real falhou no loop do agente; degradando para "
                           "o mock determinístico.", exc_info=True)
            real = False
            client = mock_client
            response = client.invoke(system=system, messages=messages,
                                     tools=tools_schema, ctx=ctx)
        model_id = response.get("model") or model_id
        usage = response.get("usage") or {}
        input_tokens += usage.get("input_tokens") or 0
        output_tokens += usage.get("output_tokens") or 0

        content = response.get("content", [])
        messages.append({"role": "assistant", "content": content})

        if response.get("stop_reason") == "tool_use":
            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                result = execute_tool(block["name"], block.get("input"), ctx)
                ok = not (isinstance(result, dict) and "error" in result)
                tools_called.append({"name": block["name"], "ok": ok})
                results_by_tool[block["name"]] = result
                if ok:
                    actions.append({"name": block["name"], "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = "".join(b.get("text", "") for b in content
                                 if b.get("type") == "text")
            break

    latency_ms = int((time.time() - started) * 1000)
    decision_id = None
    if record:
        # B.2 — trilha SEMPRE registrada (mock incluído). Digest minimizado.
        dec = record_decision(
            ctx.get("student"), trigger_type,
            input_digest=input_digest,
            model_id=model_id, mock=not real,
            tools_called=tools_called,
            actions=[{"name": a["name"]} for a in actions],
            latency_ms=latency_ms,
            input_tokens=input_tokens, output_tokens=output_tokens)
        decision_id = getattr(dec, "decision_id", None)
        # B.5/B.6 — itens que entraram na fila de aprovação nesta execução ficam
        # LIGADOS à decisão (alerts.decision_id): é o que permite ao approve/
        # reject do tutor marcar o outcome (aceita/dispensada) desta decisão.
        if decision_id:
            queued_ids = [a["result"]["alert_id"] for a in actions
                          if isinstance(a.get("result"), dict)
                          and a["result"].get("alert_id")
                          and a["result"].get("status") == "aguardando_aprovacao"
                          # dedup = item de uma execução anterior; mantém o link
                          # com a decisão que de fato o criou.
                          and not a["result"].get("dedup")]
            if queued_ids:
                from edubot.data.models.alerts import Alerts
                (Alerts
                 .update(decision_id=decision_id)
                 .where(Alerts.alert_id.in_(queued_ids))
                 .execute())

    return {
        "final_text": final_text,
        "actions": actions,
        "results_by_tool": results_by_tool,
        "tools_called": tools_called,
        "iterations": iterations,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimate_cost(model_id, input_tokens, output_tokens) if real else 0.0,
        "mock": not real,
        "model_id": model_id,
        "decision_id": decision_id,
    }
