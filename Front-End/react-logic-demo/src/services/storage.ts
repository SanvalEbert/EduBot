// Acesso a Web Storage à prova de iframe de terceiro.
//
// POR QUE ISTO EXISTE
//
// Quando o EduBot roda embutido por <iframe> num LMS (o caso do Canvas), o
// navegador trata o storage como sendo de TERCEIRO. Se o aluno tiver cookies de
// terceiros desativados — que é justamente o perfil mais preocupado com
// privacidade — o acesso não devolve `null`: ele **lança `SecurityError`**.
//
// O `typeof sessionStorage === "undefined"` que existia em events.ts não protege
// contra isso. O objeto EXISTE; é o acesso que é negado.
//
// O estrago não seria um evento perdido. `getToken()` é chamado no início de
// toda requisição à API e de `track()`; `App.tsx` lê as flags de consentimento e
// de onboarding durante a MONTAGEM do app. Uma exceção em qualquer um desses
// pontos derruba a aplicação inteira antes de o primeiro evento ser emitido — e
// só para uma parcela dos alunos, o que torna a falha quase invisível em teste.
//
// A degradação aqui é para memória: a sessão passa a viver enquanto a aba
// estiver aberta. É perda aceitável e documentada — com LTI a identidade vem do
// launch a cada abertura, então nem chega a ser perda.
//
// Ver RASTREIO_DENTRO_DO_CANVAS.md §4.

type Store = "local" | "session";

/** Espelho em memória, usado quando o storage real é inacessível. */
const memoria = new Map<string, string>();

const chaveMemoria = (store: Store, key: string) => `${store}:${key}`;

/** Resolve o objeto de storage. Pode lançar — o chamador trata. */
const nativo = (store: Store): Storage =>
  store === "local" ? window.localStorage : window.sessionStorage;

/**
 * Lê uma chave. Devolve `null` quando não existe — nunca lança.
 *
 * Em ambiente sem storage acessível, cai para o espelho em memória, de modo que
 * um `safeSet` seguido de `safeGet` continua coerente dentro da mesma aba.
 */
export function safeGet(store: Store, key: string): string | null {
  try {
    return nativo(store).getItem(key);
  } catch {
    return memoria.get(chaveMemoria(store, key)) ?? null;
  }
}

/** Grava uma chave. Nunca lança. */
export function safeSet(store: Store, key: string, value: string): void {
  try {
    nativo(store).setItem(key, value);
  } catch {
    // Cobre tanto o storage bloqueado (SecurityError) quanto a cota estourada
    // (QuotaExceededError) — em ambos, seguir em memória é melhor que quebrar.
    memoria.set(chaveMemoria(store, key), value);
  }
}

/** Remove uma chave. Nunca lança. Limpa também o espelho, senão um logout
 *  deixaria o token vivo em memória. */
export function safeRemove(store: Store, key: string): void {
  try {
    nativo(store).removeItem(key);
  } catch {
    /* ignora: o essencial é limpar o espelho abaixo */
  }
  memoria.delete(chaveMemoria(store, key));
}

/**
 * `true` se o storage real está acessível. Só para diagnóstico — a aplicação não
 * deve ramificar por isto; use `safeGet`/`safeSet` e siga em frente.
 */
export function storageDisponivel(store: Store): boolean {
  try {
    const sonda = "__edubot_probe__";
    nativo(store).setItem(sonda, "1");
    nativo(store).removeItem(sonda);
    return true;
  } catch {
    return false;
  }
}
