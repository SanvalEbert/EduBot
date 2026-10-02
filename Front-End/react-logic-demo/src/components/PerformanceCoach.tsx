/*
MELHORIA (Roteiro Cena 3) — "EduBot fala com você".

Um personagem virtualizado (CompanionAvatar — mascote EduBot ou a persona 3D
escolhida) que conversa com o aluno sobre o progresso dele, em "Meu Desempenho".
Por padrão a fala é GERADA localmente a
partir dos dados do perfil (offline, sem custo). O botão "Versão do EduBot (IA)"
pede um texto mais natural ao Claude na AWS Bedrock — SOB DEMANDA (controle de
custo). A fala pode ser OUVIDA com a boca do avatar animada.
*/
import { Pause, Play, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { StudentProfile, getCoachMessage } from "../services/api";
import { Lang, useLanguage } from "../i18n";
import { useSpeech } from "../hooks/useSpeech";
import { CompanionAvatar } from "./brand/CompanionAvatar";
import { AVATAR_PERSONAS, personaTagline } from "./brand/avatars";
import { setPersona } from "../services/persona";
import { useToast } from "./ui/Toast";

// Opções do seletor de avatar do card "Meu Desempenho": o mascote EduBot (2D,
// sempre disponível) + os cientistas 3D (Einstein, Curie). `persona: null` = EduBot.
const AVATAR_OPTIONS = [
  { id: "edubot", label: "EduBot", persona: null },
  ...AVATAR_PERSONAS.map((p) => ({
    id: p.id,
    label: p.variant === "einstein" ? "Einstein" : "Curie",
    persona: p,
  })),
];

// Fala gerada localmente a partir dos dados do aluno (calorosa e natural).
function buildCoachMessage(profile: StudentProfile, lang: Lang): string {
  const nome = (profile.estudante.nome || "").split(" ")[0];
  const consumo = profile.recursos.percentual_consumido;
  const desenvolvidas = profile.competencias.filter((c) => c.status === "desenvolvida");
  const fraca = [...profile.competencias]
    .filter((c) => c.total_questoes > 0)
    .sort((a, b) => (b.taxa_erro ?? 0) - (a.taxa_erro ?? 0))[0];
  const dias = profile.dias_sem_acesso;
  const nDev = desenvolvidas.length;
  const temFraca = fraca && (fraca.taxa_erro ?? 0) > 0.5;

  if (lang === "en") {
    const parts: string[] = [`Hey ${nome}, great to see you here!`];
    if (dias != null && dias > 7) parts.push(`It's been ${dias} days since we last talked — let's ease back into it at your own pace.`);
    let progress = `So far you've explored ${consumo}% of your materials`;
    if (nDev > 0) progress += ` and you're already solid on ${nDev} competenc${nDev > 1 ? "ies" : "y"}`;
    parts.push(progress + ".");
    if (temFraca) parts.push(`I noticed "${fraca.nome}" is still challenging you a bit — how about we reinforce it together?`);
    parts.push("Keep it up — every step counts, and you're clearly growing!");
    return parts.join(" ");
  }

  const parts: string[] = [`Oi, ${nome}, que bom te ver por aqui!`];
  if (dias != null && dias > 7) parts.push(`Faz ${dias} dias que a gente não conversa — vamos retomar com calma, no seu ritmo.`);
  let progresso = `Até agora você já explorou ${consumo}% dos seus materiais`;
  if (nDev > 0) progresso += ` e já está firme em ${nDev} competência${nDev > 1 ? "s" : ""}`;
  parts.push(progresso + ".");
  if (temFraca) parts.push(`Reparei que "${fraca.nome}" ainda está te desafiando um pouquinho — que tal reforçarmos juntos?`);
  parts.push("Continue assim — cada passo conta, e dá pra ver que você está evoluindo!");
  return parts.join(" ");
}

export const PerformanceCoach = ({ profile }: { profile: StudentProfile }) => {
  const { lang, t } = useLanguage();
  const { speak, stop, speaking, supported, visemeRef } = useSpeech();
  const toast = useToast();

  const localMessage = useMemo(() => buildCoachMessage(profile, lang), [profile, lang]);
  const [message, setMessage] = useState(localMessage);
  const [aiLoading, setAiLoading] = useState(false);
  const [fromAi, setFromAi] = useState(false);
  // AV.1/AV.2 (Plano 3): personas são LIVRES (sem cadeado) e a escolha vem do
  // servidor (profile.estudante.persona) — funciona com a gamificação desligada.
  const [avatarId, setAvatarId] = useState<string>(() => profile.estudante.persona || "edubot");
  const selected = AVATAR_OPTIONS.find((o) => o.id === avatarId) ?? AVATAR_OPTIONS[0];

  // Ao trocar de idioma (ou perfil), volta para o texto local
  useEffect(() => {
    setMessage(localMessage);
    setFromAi(false);
  }, [localMessage]);

  const askAi = async () => {
    setAiLoading(true);
    try {
      const { message: aiMsg } = await getCoachMessage(lang);
      if (aiMsg) {
        setMessage(aiMsg);
        setFromAi(true);
      } else {
        toast.error(t("IA indisponível agora — usando a versão local.", "AI unavailable right now — using the local version."));
      }
    } catch {
      toast.error(t("Não foi possível falar com a IA agora.", "Couldn't reach the AI right now."));
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="mb-6 overflow-hidden rounded-[8px] border border-line bg-gradient-to-br from-indigo-50 to-white p-6 shadow-soft">
      <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
        <div className="flex shrink-0 flex-col items-center gap-2">
          {/* AV.3: componente único — mascote 2D ou cientista 3D (com lip-sync
              por visemas) e fallback automático se o WebGL falhar. */}
          <CompanionAvatar personaId={avatarId} speaking={speaking} visemeRef={visemeRef} size={140} />

          {/* Seletor de personagem: EduBot + cientistas — todos LIVRES (AV.1). */}
          <div className="flex flex-wrap justify-center gap-1.5">
            {AVATAR_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                onClick={() => {
                  setAvatarId(opt.id);
                  setPersona(opt.id);   // AV.2: persiste no servidor + cache local
                }}
                aria-pressed={avatarId === opt.id}
                title={opt.label}
                className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition ${
                  avatarId === opt.id
                    ? "bg-brand text-white"
                    : "border border-line bg-white text-muted hover:bg-slate-50"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {selected.persona && (
            <span className="max-w-[160px] text-center text-xs text-muted">
              {personaTagline(selected.persona, lang)}
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm font-bold text-brand">
            <Sparkles size={16} /> {t("EduBot fala com você", "EduBot speaks to you")}
            {fromAi && (
              <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-indigo-700">
                {t("por IA", "by AI")}
              </span>
            )}
          </div>

          {/* Balão de fala */}
          <div className="relative mt-2 rounded-[12px] border border-line bg-white p-4 text-slate-800 shadow-sm">
            <span className="absolute -left-2 top-5 hidden h-4 w-4 rotate-45 border-b border-l border-line bg-white sm:block" />
            <p className="leading-relaxed">{message}</p>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            {speaking ? (
              <button
                onClick={stop}
                className="flex h-10 items-center gap-2 rounded-[8px] bg-brand px-4 font-semibold text-white transition hover:bg-indigo-600"
              >
                <Pause size={18} /> {t("Parar", "Stop")}
              </button>
            ) : (
              <button
                onClick={() => speak(message, lang, avatarId)}
                disabled={!supported}
                className="flex h-10 items-center gap-2 rounded-[8px] bg-brand px-4 font-semibold text-white transition hover:bg-indigo-600 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                <Play size={18} /> {t("Ouvir o EduBot", "Listen to EduBot")}
              </button>
            )}

            <button
              onClick={askAi}
              disabled={aiLoading}
              className="flex h-10 items-center gap-2 rounded-[8px] border border-brand px-4 font-semibold text-brand transition hover:bg-indigo-50 disabled:opacity-60"
            >
              <Sparkles size={18} />
              {aiLoading ? t("Gerando...", "Generating...") : t("Versão do EduBot (IA)", "EduBot version (AI)")}
            </button>

            {!supported && (
              <span className="text-xs text-muted">{t("Seu navegador não suporta voz.", "Your browser doesn't support voice.")}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
