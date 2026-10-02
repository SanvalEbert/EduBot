/*
D.1 — Fila de eventos de aprendizado (xAPI-lite) no cliente.

Mesmo padrão do sync de progresso do OvaReader: os eventos são acumulados em
memória e enviados em LOTE a cada 15 s (e no `pagehide`, com keepalive, para não
perder os últimos ao fechar a aba). Assim um play/pause/seek ou uma resposta de
quiz não vira uma requisição por clique.

Uso:
  import { track } from "../services/events";
  track("opened", "ova", ovaId, { perc: 0 });
  track("answered", "question", questionId, { correct, response_ms });
*/
import { LearningEventInput, postEvents, getToken } from "./api";
import { safeGet, safeSet } from "./storage";

const FLUSH_INTERVAL_MS = 15_000;
const MAX_QUEUE = 50; // igual ao limite do backend por requisição

// Plano de Rastreabilidade (§2.1) — identidade da SESSÃO (aba). Vai no contexto
// de todo evento para separar sessões simultâneas do mesmo aluno (duas abas) e
// reconstruir a linha do tempo de uma sessão de estudo. Fica em sessionStorage
// (morre com a aba, que é exatamente o escopo de "sessão") e não identifica a
// pessoa — o aluno já vem do token no backend.
const SESSION_ID_KEY = "edubot.sessionId";

const newId = (): string =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

export function sessionId(): string {
  // O `typeof sessionStorage === "undefined"` que existia aqui NAO protegia o
  // caso real do iframe: o objeto existe, o acesso e que e negado. safeGet
  // cobre os dois (ver services/storage.ts).
  let id = safeGet("session", SESSION_ID_KEY);
  if (!id) {
    id = newId();
    safeSet("session", SESSION_ID_KEY, id);
  }
  return id;
}

let queue: LearningEventInput[] = [];
let timer: ReturnType<typeof setInterval> | null = null;
let listenersBound = false;

function ensureRunning() {
  if (timer === null) {
    timer = setInterval(() => void flush(), FLUSH_INTERVAL_MS);
  }
  if (!listenersBound && typeof window !== "undefined") {
    // pagehide cobre fechar a aba / navegar para fora melhor que unload.
    window.addEventListener("pagehide", () => void flush(true));
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") void flush(true);
    });
    listenersBound = true;
  }
}

export function track(
  verb: string,
  objectType: string,
  objectId?: number | null,
  context?: Record<string, unknown>
) {
  // Sem sessão não há para quem atribuir o evento (o aluno vem do token).
  if (!getToken()) return;
  queue.push({
    verb,
    object_type: objectType,
    object_id: objectId ?? null,
    // §2.1: o session_id acompanha TODO evento — quem chama não precisa lembrar.
    context: { ...(context ?? {}), session_id: sessionId() },
    occurred_at: new Date().toISOString()
  });
  ensureRunning();
  // Se encheu o lote, faz flush imediato para não estourar o limite do backend.
  if (queue.length >= MAX_QUEUE) void flush();
}

export async function flush(keepalive = false): Promise<void> {
  if (queue.length === 0 || !getToken()) return;
  const batch = queue.splice(0, MAX_QUEUE);
  try {
    await postEvents(batch, { keepalive });
  } catch {
    // Best-effort: em falha, devolve o lote à fila para tentar no próximo ciclo
    // (a menos que seja o flush final de unload, quando não há próximo ciclo).
    if (!keepalive) queue = batch.concat(queue);
  }
}
