/*
U.5 — Onboarding no primeiro login, apresentado pelo avatar FALANTE do EduBot
(V.2). Três passos curtos que explicam a plataforma:
  1) seus módulos estão aqui;
  2) o quiz libera depois da leitura;
  3) eu aviso você por aqui (o sino / a caixa de recomendações).

Acessível (U.7): role="dialog" + aria-modal, foco preso no modal, Esc fecha e o
foco volta ao documento; a fala de cada passo respeita o mesmo fallback do V.1.
Uma flag em localStorage evita reexibir.
*/
import { ArrowRight, Bell, BookOpen, Lock, Volume2 } from "lucide-react";
import { useRef, useState } from "react";
import { CompanionAvatar } from "./brand/CompanionAvatar";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { useSpeech } from "../hooks/useSpeech";
import { useLanguage } from "../i18n";
import { safeGet, safeSet, safeRemove } from "../services/storage";

export const ONBOARDING_FLAG = "edubot.onboarding.v1";

interface OnboardingModalProps {
  studentName?: string;
  persona?: string;
  onDone: () => void;
}

export const OnboardingModal = ({ studentName, persona = "edubot", onDone }: OnboardingModalProps) => {
  const { lang, t } = useLanguage();
  const { speak, stop, speaking, supported, visemeRef } = useSpeech();
  const [step, setStep] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);

  const first = (studentName || "").split(" ")[0];
  const steps = [
    {
      icon: BookOpen,
      title: t("Seus módulos estão aqui", "Your modules are here"),
      text: t(
        `Oi${first ? ", " + first : ""}! Eu sou o EduBot. Seus módulos de estudo ficam em "Área de Conteúdo" — é por lá que você começa.`,
        `Hi${first ? ", " + first : ""}! I'm EduBot. Your study modules live under "Content" — that's where you start.`
      ),
    },
    {
      icon: Lock,
      title: t("O quiz libera após a leitura", "The quiz unlocks after reading"),
      text: t(
        "Cada quiz abre depois que você consome o conteúdo do módulo. Assim você chega nele já preparado.",
        "Each quiz unlocks after you consume the module's content, so you get there already prepared."
      ),
    },
    {
      icon: Bell,
      title: t("Eu aviso você por aqui", "I'll nudge you right here"),
      text: t(
        "Quando eu tiver uma recomendação — retomar um assunto, revisar, reforçar — ela aparece no seu painel. Fique de olho!",
        "When I have a recommendation — resume a topic, review, reinforce — it shows up on your dashboard. Keep an eye out!"
      ),
    },
  ];
  const current = steps[step];
  const isLast = step === steps.length - 1;

  const finish = () => {
    stop();
    safeSet("local", ONBOARDING_FLAG, "1");
    onDone();
  };

  const next = () => {
    stop();
    if (isLast) finish();
    else setStep((s) => s + 1);
  };

  // AC.1 (Plano 4): foco preso no diálogo (foco inicial no próprio diálogo);
  // Esc encerra o onboarding e devolve o foco a quem o tinha.
  useFocusTrap(dialogRef, { active: true, onEscape: finish, initialFocusRef: dialogRef });

  const Icon = current.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="onb-title"
        tabIndex={-1}
        className="w-full max-w-lg rounded-[8px] bg-white p-8 shadow-soft outline-none"
      >
        <div className="flex flex-col items-center gap-4 text-center">
          <CompanionAvatar personaId={persona} size={96} speaking={speaking} visemeRef={visemeRef} />
          {/* AC.1: o passo atual é anunciado ao avançar (região viva atômica) —
              o foco permanece no botão "Próximo" (bom para Enter repetido). */}
          <div aria-live="polite" aria-atomic="true" className="flex flex-col items-center gap-4">
            <div className="flex items-center gap-2 text-brand">
              <Icon size={20} aria-hidden="true" />
              <h1 id="onb-title" className="text-2xl font-bold text-ink">{current.title}</h1>
            </div>
            <p className="max-w-md leading-relaxed text-slate-700">{current.text}</p>
            <span className="sr-only">{t(`Passo ${step + 1} de ${steps.length}`, `Step ${step + 1} of ${steps.length}`)}</span>
          </div>

          {supported && (
            <button
              onClick={() => (speaking ? stop() : speak(current.text, lang, persona))}
              className="flex h-9 items-center gap-2 rounded-[8px] border border-brand px-3 text-sm font-semibold text-brand transition hover:bg-indigo-50"
            >
              <Volume2 size={16} /> {speaking ? t("Parar", "Stop") : t("Ouvir", "Listen")}
            </button>
          )}
        </div>

        {/* indicador de passos */}
        <div className="mt-6 flex items-center justify-center gap-2" aria-hidden="true">
          {steps.map((_, i) => (
            <span key={i} className={`h-2 rounded-full transition-all ${i === step ? "w-6 bg-brand" : "w-2 bg-slate-300"}`} />
          ))}
        </div>

        <div className="mt-6 flex items-center justify-between">
          <button onClick={finish} className="text-sm font-semibold text-muted hover:text-ink">
            {t("Pular", "Skip")}
          </button>
          <button
            onClick={next}
            className="flex h-11 items-center gap-2 rounded-[8px] bg-brand px-5 font-bold text-white transition hover:bg-indigo-600"
          >
            {isLast ? t("Começar", "Get started") : t("Próximo", "Next")}
            <ArrowRight size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};
