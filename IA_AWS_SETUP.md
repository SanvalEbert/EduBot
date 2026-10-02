# Ligar a IA real (AWS Bedrock) — passo a passo

A plataforma já está **pronta para a IA real**. Hoje o "cérebro" roda **mockado**
(determinístico, sem custo). Quando suas credenciais da AWS estiverem prontas,
ligar o Claude de verdade é **só configurar variáveis de ambiente — zero
mudança de código**.

## O que já está pronto

- Camada de provider única: [Back-End/edubot/agent/llm.py](Back-End/edubot/agent/llm.py) (mock | bedrock | anthropic).
- Os **três** agentes já usam essa camada:
  - **Tutor do OVA** (chat) — [edubot/agent/tutor.py](Back-End/edubot/agent/tutor.py)
  - **Recomendação geral** — [edubot/agent/agent.py](Back-End/edubot/agent/agent.py)
  - **Agente de tool-use (OVA de reforço)** — [edubot/agent/personalized.py](Back-End/edubot/agent/personalized.py)
- SDK `anthropic[bedrock]` já instalado na imagem do backend (cliente
  `AnthropicBedrockMantle` verificado e disponível).
- `compose.yaml` repassa as variáveis ao container do Flask, com defaults
  seguros (fica mockado se nada for definido).

## Ativar (Bedrock)

1. No **AWS Bedrock**, garanta **acesso ao modelo** Claude na região escolhida
   (Console → Bedrock → *Model access*).
2. Crie um arquivo **`.env` na raiz do projeto** (mesma pasta do `compose.yaml`):

   ```env
   EDUBOT_LLM_PROVIDER=bedrock
   EDUBOT_LLM_MODEL=claude-sonnet-4-6        # ou claude-opus-4-8 (mais capaz)
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   # AWS_SESSION_TOKEN=...                   # só se usar credenciais temporárias
   ```

   > O id do modelo recebe o prefixo `anthropic.` automaticamente na Bedrock.

3. Suba de novo:

   ```bash
   docker compose up -d
   ```

4. Teste o chat do OVA (Conteúdos → Abrir conteúdo → Tutor IA). A resposta
   agora vem do Claude real; o campo `mock` da resposta fica `false`.

   Verificação rápida por API:
   ```bash
   curl -s http://localhost:5010/login -H "Content-Type: application/json" \
     -d '[{"ra":"1","password":"1"}]'   # pegue o token
   curl -s http://localhost:5010/edubot/tutor-chat \
     -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \
     -d '[{"ova_id":1,"context":"# Computacao Quantica\n## Superposicao\nUm qubit pode estar em 0 e 1.","messages":[{"role":"user","content":"O que e superposicao?"}]}]'
   # -> "mock": false
   ```

## Alternativa: API direta da Anthropic (sem AWS)

```env
EDUBOT_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
EDUBOT_LLM_MODEL=claude-sonnet-4-6
```

## Voltar para o mock

Apague o `.env` (ou `EDUBOT_LLM_PROVIDER=mock`) e `docker compose up -d`.

## Notas

- **Grounding:** o tutor sempre recebe o material do OVA no *system prompt*, então
  o Claude real responde preso ao conteúdo da mesma forma que o mock.
- **Fallback:** se a chamada real falhar (credencial/rede), o tutor e a
  recomendação caem automaticamente no mock para não quebrar a experiência.
- **Custo:** Sonnet é mais econômico; Opus 4.8 é mais capaz. Defina em
  `EDUBOT_LLM_MODEL`.
