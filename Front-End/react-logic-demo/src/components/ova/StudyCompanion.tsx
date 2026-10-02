/*
CP.1 (Plano 3) — Widget do companheiro de estudo no leitor de OVA.

Personagem flutuante no canto inferior-ESQUERDO (o botão do tutor fica à direita):
o avatar escolhido (CompanionAvatar, com lip-sync) + um balão de fala com as
mensagens do motor de gatilhos (useCompanionScript).

Interação (feedback do usuário): CLICAR no personagem abre um MENU de ações — o
gesto natural "clico nele e vejo o que dá pra fazer": tirar dúvida com o tutor,
ouvir a dica atual, silenciar e ocultar. O balão de fala continua aparecendo
sozinho nos gatilhos (abrir/50%/concluir/quiz) com ▶ ouvir e dispensar.

A11y (AC.2 do Plano 4): o menu segue o padrão Menu Button do WAI-ARIA APG —
abre por clique OU Enter/Espaço/↓, o foco entra no 1º item, ↑/↓/Home/End navegam,
Esc fecha e devolve o foco ao boneco, Tab fecha. O botão do avatar tem aria-label
(o canvas 3D não teria nome). O balão é aria-live="polite"; respeita
prefers-reduced-motion (via CompanionAvatar/CSS).
*/
import { KeyboardEvent, MutableRefObject, useEffect, useRef, useState } from "react";
import { Bot, EyeOff, MessageCircle, MoreHorizontal, Pause, Play, Volume2, VolumeX, X } from "lucide-react";
import { CompanionAvatar } from "../brand/CompanionAvatar";
import { CompanionLine } from "../../hooks/useCompanionScript";
import { useT } from "../../i18n";

interface StudyCompanionProps {
  personaId: string;
  line: CompanionLine | null;
  speaking: boolean;
  visemeRef: MutableRefObject<string>;
  muted: boolean;
  hidden: boolean;
  onListen: () => void;
  onStop: () => void;
  onToggleMute: () => void;
  onDismiss: () => void;
  onHide: () => void;
  onShow: () => void;
  onOpenTutor: () => void;
}

interface MenuAction {
  key: string;
  icon: typeof MessageCircle;
  label: string;
  run: () => void;
}

export const StudyCompanion = ({
  personaId, line, speaking, visemeRef, muted, hidden,
  onListen, onStop, onToggleMute, onDismiss, onHide, onShow, onOpenTutor,
}: StudyCompanionProps) => {
  const t = useT();
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const avatarBtnRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const reopenerRef = useRef<HTMLButtonElement>(null);
  // Só focamos o botão de reabrir quando "Ocultar" partiu do MENU (não no
  // primeiro render de quem já estava com o companheiro oculto).
  const hidFromMenuRef = useRef(false);

  const openMenu = () => { setActiveIdx(0); setMenuOpen(true); };
  const closeMenu = (returnFocus: boolean) => {
    setMenuOpen(false);
    if (returnFocus) avatarBtnRef.current?.focus();
  };

  // Ao abrir (ou navegar por setas), foca o item ativo.
  useEffect(() => {
    if (menuOpen) itemRefs.current[activeIdx]?.focus();
  }, [menuOpen, activeIdx]);

  // Ao ocultar via menu (teclado), leva o foco ao botão de reabrir — nunca ao body.
  useEffect(() => {
    if (hidden && hidFromMenuRef.current) {
      reopenerRef.current?.focus();
      hidFromMenuRef.current = false;
    }
  }, [hidden]);

  // Oculto: só um botão discreto para reabrir (nunca vira um beco sem saída).
  if (hidden) {
    return (
      <button
        ref={reopenerRef}
        onClick={onShow}
        className="fixed bottom-4 left-4 z-30 flex h-12 w-12 items-center justify-center rounded-full bg-brand text-white shadow-soft transition hover:bg-indigo-600"
        aria-label={t("Mostrar o EduBot", "Show EduBot")}
        title={t("Mostrar o EduBot", "Show EduBot")}
      >
        <Bot size={22} aria-hidden="true" />
      </button>
    );
  }

  // Ações do menu (a de ouvir só existe quando há dica e a voz não está muda).
  const actions: MenuAction[] = [
    { key: "ask", icon: MessageCircle, label: t("Tirar uma dúvida", "Ask a question"), run: onOpenTutor },
    ...(line && !muted
      ? [{ key: "listen", icon: Play, label: t("Ouvir a dica atual", "Listen to the current tip"), run: onListen }]
      : []),
    {
      key: "mute",
      icon: muted ? VolumeX : Volume2,
      label: muted ? t("Reativar a voz", "Unmute voice") : t("Silenciar a voz", "Mute voice"),
      run: onToggleMute,
    },
    {
      key: "hide",
      icon: EyeOff,
      label: t("Ocultar o EduBot", "Hide EduBot"),
      run: () => { hidFromMenuRef.current = true; onHide(); },
    },
  ];

  // AUDITORIA P4: `actions` pode encolher com o menu ABERTO (ex.: a "dica atual"
  // desaparece se o balão for dispensado por fora do menu, via mouse, enquanto o
  // teclado navegava mais adiante na lista). Sem isso, `activeIdx` apontava para
  // fora do array e o efeito de foco virava no-op — o foco escapava para o body
  // enquanto o menu continuava visível (reproduzido: hide/mute mudam a contagem).
  useEffect(() => {
    if (menuOpen && activeIdx > actions.length - 1) setActiveIdx(actions.length - 1);
  }, [menuOpen, activeIdx, actions.length]);

  const runAction = (action: MenuAction) => {
    action.run();
    // "Ocultar" cuida do próprio foco (efeito acima); as demais devolvem ao boneco.
    closeMenu(action.key !== "hide");
  };

  const onMenuKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const len = actions.length;
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); setActiveIdx((i) => (i + 1) % len); break;
      case "ArrowUp": e.preventDefault(); setActiveIdx((i) => (i - 1 + len) % len); break;
      case "Home": e.preventDefault(); setActiveIdx(0); break;
      case "End": e.preventDefault(); setActiveIdx(len - 1); break;
      case "Escape": e.preventDefault(); closeMenu(true); break;
      case "Tab": closeMenu(false); break;
    }
  };

  const onAvatarKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    // Enter/Espaço já disparam o onClick (nativo). ↓ abre e vai ao 1º item.
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (menuOpen) setActiveIdx(0);
      else openMenu();
    }
  };

  const menuItem = "flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-slate-700 transition hover:bg-indigo-50 focus:bg-indigo-50 focus:outline-none";

  return (
    <div className="fixed bottom-4 left-4 z-30 flex max-w-[min(340px,calc(100vw-2rem))] items-end gap-2">
      <style>{`
        @keyframes ebPop { 0%{transform:scale(0.96);opacity:0} 100%{transform:scale(1);opacity:1} }
        @keyframes ebCeleb { 0%,100%{transform:translateY(0)} 30%{transform:translateY(-8px)} 55%{transform:translateY(0)} 75%{transform:translateY(-4px)} }
        .eb-pop { animation: ebPop .18s ease-out; }
        .eb-celeb { animation: ebCeleb .7s ease-in-out; }
        @media (prefers-reduced-motion: reduce) { .eb-pop, .eb-celeb { animation: none !important; } }
      `}</style>

      {/* Avatar CLICÁVEL: abre o menu de ações. */}
      <div className="relative shrink-0">
        {menuOpen && (
          <>
            {/* clique fora fecha o menu */}
            <div className="fixed inset-0 z-0" onClick={() => setMenuOpen(false)} aria-hidden="true" />
            <div
              role="menu"
              aria-labelledby="companion-menu-title"
              onKeyDown={onMenuKeyDown}
              className="eb-pop absolute bottom-full left-0 z-10 mb-2 w-56 overflow-hidden rounded-[12px] border border-line bg-white py-1 shadow-soft"
            >
              <div id="companion-menu-title" className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted">
                {t("O que posso fazer por você?", "What can I do for you?")}
              </div>
              {actions.map((action, idx) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.key}
                    ref={(el) => { itemRefs.current[idx] = el; }}
                    role="menuitem"
                    tabIndex={-1}
                    className={menuItem}
                    onClick={() => runAction(action)}
                  >
                    <Icon size={16} className="text-brand" aria-hidden="true" /> {action.label}
                  </button>
                );
              })}
            </div>
          </>
        )}

        <button
          ref={avatarBtnRef}
          onClick={() => (menuOpen ? closeMenu(false) : openMenu())}
          onKeyDown={onAvatarKeyDown}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label={t("Companheiro de estudo — abrir menu de ações", "Study companion — open actions menu")}
          className={`relative rounded-2xl outline-none ring-brand/30 transition hover:ring-4 focus-visible:ring-4 ${line?.kind === "celebrating" ? "eb-celeb" : ""}`}
        >
          <CompanionAvatar personaId={personaId} speaking={speaking} visemeRef={visemeRef} size={92} />
          {/* dica visual de que o boneco é clicável (abre menu) */}
          <span className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full border border-line bg-white text-brand shadow-sm" aria-hidden="true">
            <MoreHorizontal size={14} />
          </span>
        </button>
      </div>

      {/* Balão de fala (aparece nos gatilhos): texto + ação + ▶ ouvir. */}
      {line && (
        <div className="mb-1 min-w-0 flex-1">
          <div
            className="eb-pop relative rounded-[14px] rounded-bl-none border border-line bg-white p-3 shadow-soft"
            role="status"
            aria-live="polite"
          >
            <button
              onClick={onDismiss}
              aria-label={t("Dispensar", "Dismiss")}
              className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full border border-line bg-white text-muted shadow-sm transition hover:bg-slate-50"
            >
              <X size={12} aria-hidden="true" />
            </button>
            <p className="text-sm leading-snug text-slate-800">{line.text}</p>

            {line.action && (
              <button
                onClick={line.action.run}
                className="mt-2 rounded-full bg-brand px-3 py-1 text-xs font-semibold text-white transition hover:bg-indigo-600"
              >
                {line.action.label}
              </button>
            )}

            {!muted && (
              <div className="mt-2">
                {speaking ? (
                  <button
                    onClick={onStop}
                    className="flex items-center gap-1 rounded-full border border-line bg-slate-50 px-2 py-1 text-xs font-semibold text-brand"
                  >
                    <Pause size={12} aria-hidden="true" /> {t("Parar", "Stop")}
                  </button>
                ) : (
                  <button
                    onClick={onListen}
                    className="flex items-center gap-1 rounded-full border border-line bg-slate-50 px-2 py-1 text-xs font-semibold text-brand transition hover:bg-indigo-50"
                  >
                    <Play size={12} aria-hidden="true" /> {t("Ouvir", "Listen")}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
