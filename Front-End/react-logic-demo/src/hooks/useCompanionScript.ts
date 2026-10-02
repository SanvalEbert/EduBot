/*
CP.2 (Plano 3) — motor de falas do companheiro de estudo (100% no cliente).

Decide O QUE o personagem diz e QUANDO, com regras anti-irritação duras. O TEXTO
das falas vem do componente (i18n via useT) — este hook só gerencia a exibição e
os limites, além da telemetria (verbos novos no schema D.1, sem migration).

Regras:
  - falas ESPONTÂNEAS (marcos de leitura) respeitam cooldown de 45 s e teto de 6
    por sessão de leitura;
  - REAÇÕES a ações do aluno (quiz, botões) NÃO contam no teto e sempre aparecem;
  - fala nova SUBSTITUI a anterior (nunca empilha);
  - NENHUM áudio automático — a voz só toca via ▶ (o navegador bloqueia autoplay).
*/
import { useCallback, useRef, useState } from "react";
import { track } from "../services/events";

export type CompanionKind = "idle" | "talking" | "celebrating";

export interface CompanionAction {
  label: string;
  run: () => void;
}

export interface CompanionLine {
  text: string;
  kind: CompanionKind;
  action?: CompanionAction;
}

interface SayOpts {
  trigger: string;
  text: string;
  kind?: CompanionKind;
  action?: CompanionAction;
  /** true = fala espontânea (marco); respeita cooldown + teto. */
  spontaneous?: boolean;
}

const COOLDOWN_MS = 45_000;
const MAX_SPONTANEOUS = 6;

export function useCompanionScript(ovaId: number) {
  const [line, setLine] = useState<CompanionLine | null>(null);
  const lastSpontaneousAt = useRef(0);
  const spontaneousCount = useRef(0);
  const firedTriggers = useRef<Set<string>>(new Set());

  const say = useCallback(
    (opts: SayOpts) => {
      if (opts.spontaneous) {
        // marcos disparam UMA vez por sessão (ex.: "50%") e respeitam cooldown/teto
        if (firedTriggers.current.has(opts.trigger)) return;
        const now = Date.now();
        if (spontaneousCount.current >= MAX_SPONTANEOUS) return;
        if (now - lastSpontaneousAt.current < COOLDOWN_MS) return;
        lastSpontaneousAt.current = now;
        spontaneousCount.current += 1;
        firedTriggers.current.add(opts.trigger);
      }
      setLine({ text: opts.text, kind: opts.kind ?? "talking", action: opts.action });
      track("companion_spoke", "ova", ovaId, { trigger: opts.trigger });
    },
    [ovaId]
  );

  const dismiss = useCallback(() => {
    setLine(null);
    track("companion_dismissed", "ova", ovaId);
  }, [ovaId]);

  const listened = useCallback(() => {
    track("companion_listened", "ova", ovaId);
  }, [ovaId]);

  return { line, say, dismiss, listened };
}
