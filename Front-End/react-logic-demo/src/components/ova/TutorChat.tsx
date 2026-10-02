/*
Tutor IA por OVA — o PERSONAGEM conversa com o aluno sobre o conteúdo.

CP.4 (Plano 3):
  - o estado do chat vive no OvaReader (hook useTutorChat) — fechar/reabrir o painel
    NÃO perde a conversa (M6); este componente é a UI (input + render);
  - o header mostra a PERSONA escolhida (avatar + nome) em vez do logo genérico (M7);
  - cada resposta pode ser OUVIDA na voz da persona (▶), com a boca do avatar animada.

O tutor continua preso ao material do OVA (grounding no backend); a persona muda só
o TOM. As "Fontes" (seções que embasaram a resposta) seguem exibidas.
*/
import { BookMarked, Bot, LoaderCircle, Pause, Play, Send, User, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { ChatMessage } from "../../hooks/useTutorChat";
import { useToast } from "../ui/Toast";
import { useLanguage, useT } from "../../i18n";
import { CompanionAvatar } from "../brand/CompanionAvatar";
import { AVATAR_PERSONAS, personaName } from "../brand/avatars";
import { useSpeech } from "../../hooks/useSpeech";

interface TutorChatProps {
  ovaName: string;
  personaId: string;
  messages: ChatMessage[];
  loading: boolean;
  onAsk: (question: string) => Promise<boolean>;
  onClose: () => void;
}

function tutorName(personaId: string, lang: "pt" | "en", t: (pt: string, en: string) => string): string {
  const p = AVATAR_PERSONAS.find((x) => x.id === personaId);
  return p ? personaName(p, lang) : t("Professor Mediador", "Mediating Professor");
}

export const TutorChat = ({ ovaName, personaId, messages, loading, onAsk, onClose }: TutorChatProps) => {
  const t = useT();
  const { lang } = useLanguage();
  const { speak, stop, speaking, visemeRef } = useSpeech();
  const [input, setInput] = useState("");
  const [speakingIdx, setSpeakingIdx] = useState<number | null>(null);
  // VI.3 (Plano 4): trecho da fonte que está expandido (chave "msgIdx-srcIdx").
  // Substitui o `title` (invisível a teclado/touch) por um bloco expansível.
  const [openSource, setOpenSource] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  const SUGGESTIONS = [
    t("Resuma os principais pontos deste conteúdo", "Summarize the main points of this content"),
    t("Explique o conceito mais importante com outras palavras", "Explain the most important concept in other words"),
    t("Me dê um exemplo prático do que estudei", "Give me a practical example of what I studied"),
  ];

  useEffect(() => {
    // VI.2: `scroll-behavior: auto` do CSS não afeta o `behavior` explícito do
    // scrollTo — respeitamos a preferência aqui.
    const reduce = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [messages, loading]);

  // AC.3 (Plano 4): região viva DEDICADA — anuncia só a última fala relevante
  // (o "pensando" enquanto carrega, ou a resposta do tutor ao chegar). Um
  // aria-live na lista rolável faria o leitor de tela repetir mensagens antigas
  // a cada re-render do React.
  const liveMessage = useMemo(() => {
    if (loading) return t("O tutor está pensando...", "The tutor is thinking...");
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role !== "user") return messages[i].content;
    }
    return "";
  }, [messages, loading, t]);

  // Quando a fala termina (speaking cai), limpa o índice em reprodução.
  useEffect(() => {
    if (!speaking) setSpeakingIdx(null);
  }, [speaking]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || loading) return;
    setInput("");
    const ok = await onAsk(text);
    if (!ok) {
      toast.error(t("Não foi possível falar com o tutor agora. Tente novamente.", "Couldn't reach the assistant right now. Try again."));
      setInput(text);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    ask(input);
  };

  const listen = (idx: number, content: string) => {
    setSpeakingIdx(idx);
    speak(content, lang, personaId); // voz da persona (AV.4)
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[8px] border border-line bg-white shadow-soft">
      <header className="flex items-center justify-between gap-3 border-b border-line bg-gradient-to-r from-brand to-indigo-500 px-4 py-3 text-white">
        <div className="flex min-w-0 items-center gap-3">
          <div className="h-11 w-11 shrink-0 overflow-hidden rounded-full bg-white/20">
            <CompanionAvatar personaId={personaId} speaking={speaking} visemeRef={visemeRef} size={44} />
          </div>
          <div className="min-w-0">
            <div className="truncate font-bold leading-tight">{tutorName(personaId, lang, t)}</div>
            <div className="truncate text-xs text-white/80">{t("Conversando sobre", "Talking about")} “{ovaName}”</div>
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label={t("Fechar", "Close")}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition hover:bg-white/20"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      {/* AC.3: região viva dedicada (invisível) — leitor de tela anuncia a resposta do tutor. */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{liveMessage}</div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-slate-50 p-4">
        {messages.map((message, index) => {
          const isUser = message.role === "user";
          return (
            <div key={index} className={`flex gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                  isUser ? "bg-coral text-white" : "bg-brand text-white"
                }`}
                aria-hidden="true"
              >
                {isUser ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className={`flex max-w-[80%] flex-col ${isUser ? "items-end" : "items-start"}`}>
                <div
                  className={`whitespace-pre-wrap rounded-[12px] px-4 py-2.5 text-sm leading-relaxed ${
                    isUser
                      ? "rounded-tr-none bg-brand text-white"
                      : "rounded-tl-none border border-line bg-white text-slate-700"
                  }`}
                >
                  {/* AC.3: quem falou (só para leitor de tela — os avatares são decorativos). */}
                  <span className="sr-only">{isUser ? t("Você:", "You:") : `${tutorName(personaId, lang, t)}:`} </span>
                  {message.content}
                </div>

                {/* Ouvir a resposta na voz da persona (não na saudação inicial) */}
                {!isUser && index > 0 && (
                  <button
                    onClick={() => (speakingIdx === index ? stop() : listen(index, message.content))}
                    className="mt-1 flex items-center gap-1 rounded-full border border-line bg-white px-2 py-0.5 text-xs font-semibold text-brand transition hover:bg-indigo-50"
                  >
                    {speakingIdx === index ? <Pause size={11} aria-hidden="true" /> : <Play size={11} aria-hidden="true" />}
                    {speakingIdx === index ? t("Parar", "Stop") : t("Ouvir", "Listen")}
                  </button>
                )}

                {/* Referenciação automática: seções do OVA que embasaram a resposta.
                    VI.3: o trecho (antes num `title`) abre num bloco expansível. */}
                {!isUser && message.sources && message.sources.length > 0 && (
                  <div className="mt-1.5 flex flex-col gap-1.5">
                    <div className="flex flex-wrap gap-1.5">
                      {message.sources.map((source, sourceIndex) => {
                        const key = `${index}-${sourceIndex}`;
                        const isOpen = openSource === key;
                        return (
                          <button
                            key={sourceIndex}
                            type="button"
                            onClick={() => setOpenSource(isOpen ? null : key)}
                            aria-expanded={isOpen}
                            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition ${
                              isOpen ? "border-brand bg-indigo-50 text-brand" : "border-line bg-slate-50 text-muted hover:bg-indigo-50"
                            }`}
                          >
                            <BookMarked size={12} className="text-brand" aria-hidden="true" />
                            {source.secao}
                          </button>
                        );
                      })}
                    </div>
                    {message.sources.map((source, sourceIndex) =>
                      openSource === `${index}-${sourceIndex}` ? (
                        <p
                          key={`trecho-${sourceIndex}`}
                          className="rounded-[8px] border border-line bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600"
                        >
                          {source.trecho}
                        </p>
                      ) : null
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-white" aria-hidden="true">
              <Bot size={16} />
            </div>
            <div className="flex items-center gap-2 rounded-[12px] rounded-tl-none border border-line bg-white px-4 py-2.5 text-sm text-muted">
              <LoaderCircle size={15} className="animate-spin" aria-hidden="true" />
              {t("Pensando...", "Thinking...")}
            </div>
          </div>
        )}

        {messages.length === 1 && !loading && (
          <div className="space-y-2 pt-2">
            <p className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">{t("Sugestões", "Suggestions")}</p>
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => ask(suggestion)}
                className="block w-full rounded-[8px] border border-line bg-white px-3 py-2 text-left text-sm text-slate-700 transition hover:border-brand hover:bg-indigo-50"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>

      <form onSubmit={onSubmit} className="flex items-center gap-2 border-t border-line bg-white p-3">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t("Pergunte sobre este conteúdo...", "Ask about this content...")}
          aria-label={t("Pergunte sobre este conteúdo", "Ask about this content")}
          className="h-11 w-full rounded-[8px] border border-line bg-slate-50 px-4 text-sm text-ink outline-none focus:border-brand"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          aria-label={t("Enviar", "Send")}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[8px] bg-brand text-white transition hover:bg-indigo-600 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <Send size={18} aria-hidden="true" />
        </button>
      </form>
    </div>
  );
};
