/*
INTEGRAÇÃO (4.1) — Player de ÁUDIO/PODCAST em React (espelho do componente
vanilla Front-End/files/js/components/audio-player.js).

Rastreia o tempo REAL de escuta (segundos com o áudio tocando, acumulados
mesmo com pause/seek) e a conclusão. Reporta a cada 10s de escuta, no pause
e no fim.
*/
import { Headphones } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useT } from "../../i18n";
import { MediaProgress } from "./VideoPlayer";
import { track } from "../../services/events";

const COMPLETED_PERC = 90;
const REPORT_EVERY_S = 10;

interface AudioPlayerProps {
  url: string | null;
  title: string;
  durationSeconds: number | null;
  initialSeconds: number;
  // Fase 0 (E0.3): id do recurso para as transições (play/pause/fim) virarem
  // eventos xAPI-lite, como no vídeo.
  resourceId?: number;
  onProgress: (progress: MediaProgress) => void;
}

// NOTA (Plano de Rastreabilidade §3.1): diferente do vídeo, o áudio NÃO tem gate
// de visibilidade — ouvir podcast com a aba em segundo plano é escuta legítima.
// O tempo aqui já era medido corretamente (1s por segundo tocando); a Fase 1 só
// acrescentou as transições como eventos.
export const AudioPlayer = ({ url, title, durationSeconds, initialSeconds, resourceId, onProgress }: AudioPlayerProps) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const listenedRef = useRef(initialSeconds);
  const lastReportedRef = useRef(initialSeconds);
  const tickerRef = useRef<number | null>(null);
  const [listened, setListened] = useState(initialSeconds);
  const t = useT();

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const totalDuration = () =>
      audio.duration && isFinite(audio.duration) ? audio.duration : durationSeconds ?? 0;

    const currentPerc = () => {
      const total = totalDuration();
      return total ? Math.min(100, Math.round((100 * listenedRef.current) / total)) : 0;
    };

    const report = (completed = false) => {
      lastReportedRef.current = listenedRef.current;
      onProgress({
        seconds: Math.round(listenedRef.current),
        perc: currentPerc(),
        completed: completed || currentPerc() >= COMPLETED_PERC
      });
    };

    const stopTicker = () => {
      if (tickerRef.current) {
        window.clearInterval(tickerRef.current);
        tickerRef.current = null;
      }
    };

    const position = () => Math.round(audio.currentTime || 0);

    const onPlay = () => {
      track("played", "resource", resourceId, { position_s: position() });
      if (tickerRef.current) return;
      tickerRef.current = window.setInterval(() => {
        listenedRef.current += 1;
        setListened(listenedRef.current);
        if (listenedRef.current - lastReportedRef.current >= REPORT_EVERY_S) report();
      }, 1000);
    };
    const onPause = () => {
      stopTicker();
      track("paused", "resource", resourceId, { position_s: position() });
      report();
    };
    const onEnded = () => {
      stopTicker();
      track("completed", "resource", resourceId, { position_s: position() });
      report(true);
    };
    const onRateChange = () => {
      track("rate_changed", "resource", resourceId, { rate: audio.playbackRate });
    };

    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("ratechange", onRateChange);
    return () => {
      stopTicker();
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("ratechange", onRateChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, durationSeconds, resourceId]);

  const minutes = Math.floor(listened / 60);
  const seconds = Math.round(listened % 60);
  const total = durationSeconds ?? 0;
  const perc = total ? Math.min(100, Math.round((100 * listened) / total)) : 0;

  return (
    <div className="rounded-[8px] border border-line bg-white p-5">
      <h3 className="flex items-center gap-2 font-bold text-ink">
        <Headphones size={20} className="text-brand" />
        {title}
      </h3>
      <audio ref={audioRef} controls preload="metadata" src={url ?? undefined} className="mt-3 w-full" />
      <div className="mt-2 text-sm text-muted">
        {t("Tempo de escuta", "Listening time")}: {minutes}m{String(seconds).padStart(2, "0")}s{total ? ` (${perc}%)` : ""}
      </div>
    </div>
  );
};
