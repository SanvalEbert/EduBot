/*
V.1 — Voz do EduBot: AWS Polly neural (com lip-sync por visemas) e FALLBACK para
a Web Speech API do navegador.

Mantém a interface original (`speak/stop/speaking/supported`) e adiciona
`visemeRef` (viseme atual, p/ a boca do avatar). O fluxo:
  1. tenta POST /edubot/speak (Polly) — toca o mp3 e agenda a timeline de visemas
     com requestAnimationFrame contra audio.currentTime;
  2. se a síntese não estiver disponível (sem credencial Polly / falha), cai no
     Web Speech como antes. A Bedrock API key NÃO cobre Polly, então o fallback é
     o caminho normal até haver credencial de voz.
*/
import { useCallback, useEffect, useRef, useState } from "react";
import { Viseme, apiUrl, synthesizeSpeech } from "../services/api";
import { track } from "../services/events";

// Nomes de vozes de melhor qualidade (neurais/online) para o fallback Web Speech.
const PREFERRED = [
  "natural", "neural", "online", "google",
  "francisca", "antonio", "luciana", "camila", "vitória", "vitoria", "maria",
  "aria", "jenny", "guy", "michelle", "samantha"
];

// AV.4: viés de gênero por persona no fallback Web Speech (as vozes do navegador
// são inconsistentes entre plataformas; isto só REORDENA, nunca exclui — se nada
// casar, o comportamento é idêntico ao anterior). O Polly já dá a voz certa.
const PERSONA_GENDER: Record<string, "male" | "female"> = {
  einstein: "male", curie: "female", edubot: "female",
};
const GENDER_HINTS: Record<"male" | "female", string[]> = {
  male: ["male", "masculin", "homem", "thiago", "antonio", "antônio", "ricardo",
         "daniel", "matthew", "paulo", "felipe", "guy"],
  female: ["female", "feminin", "mulher", "camila", "vitória", "vitoria", "joanna",
           "francisca", "luciana", "maria", "danielle", "aria", "jenny", "michelle"],
};

function pickVoice(
  voices: SpeechSynthesisVoice[], lang: string, persona?: string
): SpeechSynthesisVoice | undefined {
  const prefix = lang === "en" ? "en" : "pt";
  const inLang = voices.filter((v) => v.lang?.toLowerCase().startsWith(prefix));
  const pool = inLang.length ? inLang : voices;
  const gender = persona ? PERSONA_GENDER[persona] : undefined;
  const hints = gender ? GENDER_HINTS[gender] : [];
  const scored = pool
    .map((v) => {
      const name = v.name.toLowerCase();
      const rank = PREFERRED.findIndex((p) => name.includes(p));
      // casar o gênero da persona tem prioridade sobre a lista de qualidade.
      const genderMatch = hints.some((h) => name.includes(h)) ? 0 : 1;
      return { v, score: genderMatch * 1000 + (rank === -1 ? 999 : rank) };
    })
    .sort((a, b) => a.score - b.score);
  return scored[0]?.v;
}

export function useSpeech() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [speaking, setSpeaking] = useState(false);
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  // Viseme atual (p/ o avatar mapear a boca). "sil" = boca neutra/fechada.
  const visemeRef = useRef<string>("sil");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const rafRef = useRef<number | null>(null);
  // Se o Polly já se mostrou indisponível, nem tenta de novo (vai direto ao fallback).
  const pollyOffRef = useRef(false);

  useEffect(() => {
    if (!supported) return;
    const load = () => {
      voicesRef.current = window.speechSynthesis.getVoices();
    };
    load();
    window.speechSynthesis.addEventListener?.("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", load);
  }, [supported]);

  const stopTimeline = useCallback(() => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    visemeRef.current = "sil";
  }, []);

  const speakWebSpeech = useCallback(
    (text: string, lang: "pt" | "en", persona?: string) => {
      if (!supported || !text) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang === "en" ? "en-US" : "pt-BR";
      const voice = pickVoice(voicesRef.current, lang, persona);
      if (voice) utterance.voice = voice;
      utterance.rate = 0.97;
      utterance.pitch = 1.0;
      utterance.volume = 1;
      // Sem visemas do Polly: aproxima a boca alternando aberto/neutro.
      let open = false;
      const tick = () => {
        visemeRef.current = open ? "a" : "sil";
        open = !open;
      };
      const interval = window.setInterval(tick, 120);
      utterance.onstart = () => setSpeaking(true);
      const finish = () => {
        window.clearInterval(interval);
        visemeRef.current = "sil";
        setSpeaking(false);
      };
      utterance.onend = finish;
      utterance.onerror = finish;
      window.speechSynthesis.speak(utterance);
    },
    [supported]
  );

  const playPolly = useCallback(
    (audioUrl: string, visemes: Viseme[]) => {
      const audio = new Audio(apiUrl(audioUrl));
      audioRef.current = audio;
      const loop = () => {
        const tMs = audio.currentTime * 1000;
        // último viseme cujo tempo já passou
        let current = "sil";
        for (const v of visemes) {
          if (v.time_ms <= tMs) current = v.viseme;
          else break;
        }
        visemeRef.current = current;
        rafRef.current = requestAnimationFrame(loop);
      };
      audio.onplay = () => {
        setSpeaking(true);
        rafRef.current = requestAnimationFrame(loop);
      };
      const finish = () => {
        stopTimeline();
        setSpeaking(false);
      };
      audio.onended = finish;
      audio.onerror = finish;
      void audio.play().catch(finish);
    },
    [stopTimeline]
  );

  const speak = useCallback(
    async (text: string, lang: "pt" | "en", persona?: string) => {
      if (!text) return;
      // métrica V.1: cliques em "ouvir o EduBot" (evento played sobre speech)
      track("played", "session", null, { kind: "speech", lang });
      if (!pollyOffRef.current) {
        try {
          // AV.4: persona escolhe a voz (Einstein/Curie têm voz própria no Polly).
          const r = await synthesizeSpeech(text, lang, persona);
          if (r.available && r.audio_url) {
            if (supported) window.speechSynthesis.cancel();
            playPolly(r.audio_url, r.visemes ?? []);
            return;
          }
          pollyOffRef.current = true; // indisponível: não tenta mais nesta sessão
        } catch {
          pollyOffRef.current = true;
        }
      }
      speakWebSpeech(text, lang, persona);
    },
    [playPolly, speakWebSpeech, supported]
  );

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    stopTimeline();
    setSpeaking(false);
  }, [supported, stopTimeline]);

  useEffect(
    () => () => {
      if (supported) window.speechSynthesis.cancel();
      if (audioRef.current) audioRef.current.pause();
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    },
    [supported]
  );

  return { speak, stop, speaking, supported, visemeRef };
}
