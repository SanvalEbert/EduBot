/*
AC.1 (Plano 4) — useFocusTrap: prende o foco do teclado dentro de um container
enquanto ele está ativo (diálogos/modais/drawers). Sem dependência nova.

Contrato:
  - `active`: liga/desliga a armadilha (permite montar o hook sempre, na mesma
    ordem, e só atuar quando o diálogo está aberto);
  - `onEscape?`: se presente, Esc chama a função (ex.: fechar o modal); se
    ausente, Esc não faz nada (modal bloqueante, ex.: consentimento);
  - `initialFocusRef?`: elemento a focar ao abrir; default = 1º focável do
    container, ou o próprio container (que deve ter tabIndex={-1}).

Comportamento:
  - Tab no último focável volta ao primeiro; Shift+Tab no primeiro vai ao último
    (WCAG 2.1.2 — sem armadilha permanente, pois Esc/ação de fechar sempre existe
    fora do consentimento);
  - a lista de focáveis é consultada A CADA Tab (o conteúdo do diálogo muda —
    ex.: passos do onboarding);
  - ao desativar/desmontar, devolve o foco a quem o tinha antes de abrir.
*/
import { RefObject, useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "textarea:not([disabled])",
  "select:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

// Visível de verdade: getClientRects cobre também elementos position:fixed
// (o painel do tutor no mobile é fixed) — offsetParent falharia nesse caso.
const getFocusable = (container: HTMLElement): HTMLElement[] =>
  Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) => el.getClientRects().length > 0
  );

interface FocusTrapOptions {
  active: boolean;
  onEscape?: () => void;
  initialFocusRef?: RefObject<HTMLElement>;
}

export function useFocusTrap(
  containerRef: RefObject<HTMLElement>,
  { active, onEscape, initialFocusRef }: FocusTrapOptions
): void {
  // onEscape muda de identidade a cada render (funções inline); guardamos a
  // versão mais recente numa ref para NÃO recriar o efeito (que re-focaria o
  // elemento inicial a cada render).
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const initial = initialFocusRef?.current ?? getFocusable(container)[0] ?? container;
    initial.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        const cb = onEscapeRef.current;
        if (cb) {
          e.preventDefault();
          cb();
        }
        return;
      }
      if (e.key !== "Tab") return;

      const items = getFocusable(container);
      if (items.length === 0) {
        e.preventDefault();
        container.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const activeEl = document.activeElement;

      if (e.shiftKey) {
        if (activeEl === first || activeEl === container || !container.contains(activeEl)) {
          e.preventDefault();
          last.focus();
        }
      } else if (activeEl === last || !container.contains(activeEl)) {
        e.preventDefault();
        first.focus();
      }
    };

    container.addEventListener("keydown", onKeyDown);
    return () => {
      container.removeEventListener("keydown", onKeyDown);
      // AUDITORIA P4: só restaura o foco se o container REALMENTE sumiu (desmontou
      // ou ficou oculto). `active` pode virar `false` sem o diálogo fechar — ex.:
      // o painel do tutor no OvaReader desativa o trap ao cruzar o breakpoint
      // desktop (isDesktop=true) mesmo com o painel ainda aberto (lado a lado).
      // Sem essa checagem, o foco era puxado de volta ao botão que abriu o painel
      // ENQUANTO o aluno ainda digitava dentro dele (reproduzido ao redimensionar/
      // girar a tela com o chat focado).
      const stillVisible = container.isConnected && container.getClientRects().length > 0;
      if (!stillVisible) previouslyFocused?.focus?.();
    };
  }, [active, containerRef, initialFocusRef]);
}
