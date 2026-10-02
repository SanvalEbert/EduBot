/*
MELHORIA — Sistema de toasts (avisos não-bloqueantes).

Antes, falhas ao salvar progresso viravam um silencioso `console.error`: se a API
caísse, o aluno achava que tinha progredido. Agora qualquer tela pode chamar
`useToast()` para dar feedback visível de sucesso/erro. Provider montado uma vez
em main.tsx, envolvendo o App.

QF.4 (Plano 4): o toast PAUSA a contagem enquanto o mouse/foco está sobre ele
(WCAG 2.2.1 — Tempo ajustável); erros ficam mais tempo (8s vs 4s); o botão de
fechar respeita o idioma.
*/
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useT } from "../../i18n";

type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
  duration: number;
}

interface ToastContextValue {
  notify: (message: string, kind?: ToastKind) => void;
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export const useToast = (): ToastContextValue => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast precisa estar dentro de <ToastProvider>");
  return ctx;
};

const ICONS: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info
};

const STYLES: Record<ToastKind, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
  info: "border-line bg-white text-ink"
};

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const t = useT();
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  // Timers de auto-dismiss por toast — canceláveis para pausar no hover/foco.
  const timers = useRef<Map<number, number>>(new Map());

  const clearTimer = useCallback((id: number) => {
    const handle = timers.current.get(id);
    if (handle) {
      window.clearTimeout(handle);
      timers.current.delete(id);
    }
  }, []);

  const dismiss = useCallback((id: number) => {
    clearTimer(id);
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, [clearTimer]);

  const startTimer = useCallback((id: number, ms: number) => {
    clearTimer(id);
    timers.current.set(id, window.setTimeout(() => dismiss(id), ms));
  }, [clearTimer, dismiss]);

  const notify = useCallback(
    (message: string, kind: ToastKind = "info") => {
      const id = Date.now() + Math.random();
      const duration = kind === "error" ? 8000 : 4000;
      setToasts((current) => [...current, { id, kind, message, duration }]);
      startTimer(id, duration);
    },
    [startTimer]
  );

  // Limpa quaisquer timers pendentes ao desmontar o provider.
  useEffect(() => {
    const map = timers.current;
    return () => { map.forEach((handle) => window.clearTimeout(handle)); map.clear(); };
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({
      notify,
      success: (message: string) => notify(message, "success"),
      error: (message: string) => notify(message, "error")
    }),
    [notify]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* U.7: região "viva" — leitores de tela anunciam cada novo aviso. */}
      <div
        className="fixed bottom-5 right-5 z-50 flex w-80 max-w-[90vw] flex-col gap-3"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((toast) => {
          const Icon = ICONS[toast.kind];
          return (
            <div
              key={toast.id}
              role="status"
              // QF.4: pausa a contagem enquanto o ponteiro/foco está sobre o aviso;
              // ao sair, reinicia a contagem (WCAG 2.2.1).
              onMouseEnter={() => clearTimer(toast.id)}
              onMouseLeave={() => startTimer(toast.id, toast.duration)}
              onFocus={() => clearTimer(toast.id)}
              onBlur={() => startTimer(toast.id, toast.duration)}
              className={`flex items-start gap-3 rounded-[8px] border p-4 shadow-soft ${STYLES[toast.kind]}`}
            >
              <Icon size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span className="flex-1 text-sm font-medium">{toast.message}</span>
              <button
                onClick={() => dismiss(toast.id)}
                className="shrink-0 opacity-60 transition hover:opacity-100"
                aria-label={t("Fechar aviso", "Close notice")}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};
