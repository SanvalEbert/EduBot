/*
INTEGRAÇÃO (4.1) — Player de VÍDEO em React.

Recebe uma URL qualquer: YouTube -> embed via IFrame API com polling de
progresso; qualquer outra URL (upload/S3/local) -> <video> HTML5.

Plano de Rastreabilidade — Fase 1 (corrige a auditoria P2):
antes, "% assistido" era a POSIÇÃO máxima do player em checkpoints de 10% — um
seek para o fim marcava 100% sem o aluno ver nada, e `seconds` reportava a
posição, não o tempo assistido. Agora medimos três coisas distintas:

  - tempo assistido REAL: ticker de 1s que só conta com o vídeo TOCANDO e a aba
    VISÍVEL (mesmo princípio do gate de idle da leitura). Replay conta.
  - cobertura da linha do tempo: 100 baldes de 1%; o balde da posição corrente
    acende a cada tick de reprodução, então seek NÃO preenche. É a cobertura que
    define a conclusão (>= 90%).
  - posição: última (ponto de abandono / retomada) e máxima.

Transições (play/pause/seek/velocidade/fim) viram eventos xAPI-lite pela fila
existente — volume baixo, e é o que revela replays e pulos ao professor.
*/
import { useEffect, useRef, useState } from "react";
import { useT } from "../../i18n";
import { track } from "../../services/events";
import type { MediaProgress } from "../../services/mediaProgress";

// O tipo mora no serviço (camada de dados); reexportado aqui porque os
// componentes já o importavam deste módulo.
export type { MediaProgress };

const COMPLETED_PERC = 90;
// Sincroniza com o backend a cada 10s tocando (e em pause/fim/unload). O upsert
// substitui uma única linha por (aluno, recurso): custo de armazenamento zero.
const SYNC_EVERY_SECONDS = 10;
const BITMAP_SIZE = 100;

declare global {
  interface Window {
    YT?: any;
    onYouTubeIframeAPIReady?: () => void;
  }
}

let ytApiPromise: Promise<any> | null = null;
const loadYouTubeAPI = () => {
  if (ytApiPromise) return ytApiPromise;
  ytApiPromise = new Promise((resolve) => {
    if (window.YT?.Player) return resolve(window.YT);
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      resolve(window.YT);
    };
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  });
  return ytApiPromise;
};

export const youtubeIdFromUrl = (url: string | null) => {
  const match = (url ?? "").match(/(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([\w-]{6,})/);
  return match ? match[1] : null;
};

interface VideoPlayerProps {
  url: string | null;
  mediaType: string | null;
  title: string;
  // Estado já conquistado no servidor (retomada da cobertura entre sessões).
  // Substitui o antigo `initialPerc` (posição máxima), que media a coisa errada.
  initialCoverageBitmap?: string | null;
  initialCoveragePerc?: number;
  resourceId?: number;
  onProgress: (progress: MediaProgress) => void;
}

/** Bitmap vazio (nenhum balde da linha do tempo visitado). */
const emptyBitmap = () => "0".repeat(BITMAP_SIZE);

/** Normaliza o que veio do servidor para o tamanho fixo do bitmap. */
const bitmapFromServer = (stored: string | null | undefined): string => {
  if (!stored) return emptyBitmap();
  const clean = stored.slice(0, BITMAP_SIZE).replace(/[^01]/g, "0");
  return clean.padEnd(BITMAP_SIZE, "0");
};

export const VideoPlayer = ({
  url,
  mediaType,
  title,
  initialCoverageBitmap,
  initialCoveragePerc = 0,
  resourceId,
  onProgress
}: VideoPlayerProps) => {
  const slotRef = useRef<HTMLDivElement>(null);
  const [coverage, setCoverage] = useState(initialCoveragePerc);
  const [watched, setWatched] = useState(0);
  const t = useT();

  // Estado da medição vive em refs: o ticker não deve re-renderizar o player.
  const bucketsRef = useRef<string[]>(bitmapFromServer(initialCoverageBitmap).split(""));
  const unsyncedSecondsRef = useRef(0);   // assistido ainda não enviado (delta)
  const positionRef = useRef(0);          // última posição conhecida (segundos)
  const durationRef = useRef(0);
  const playingRef = useRef(false);
  const rateRef = useRef(1);

  const ytId = mediaType === "youtube" || /youtu/.test(url ?? "") ? youtubeIdFromUrl(url) : null;

  useEffect(() => {
    // Marca o balde de 1% correspondente à posição atual. Só é chamado a partir
    // do ticker de reprodução — por isso um seek não acende baldes intermediários.
    const markCurrentBucket = () => {
      const duration = durationRef.current;
      if (duration <= 0) return;
      const bucket = Math.min(
        BITMAP_SIZE - 1,
        Math.floor((BITMAP_SIZE * positionRef.current) / duration)
      );
      if (bucketsRef.current[bucket] !== "1") {
        bucketsRef.current[bucket] = "1";
        setCoverage(bucketsRef.current.filter((b) => b === "1").length);
      }
    };

    const coveragePerc = () => bucketsRef.current.filter((b) => b === "1").length;

    // Envia o acumulado da sessão: o servidor soma o delta e faz OR do bitmap.
    // Reenviar o bitmap inteiro (e não um delta) é o que dá auto-heal quando um
    // sync se perde.
    const sync = (completed = false) => {
      const delta = unsyncedSecondsRef.current;
      unsyncedSecondsRef.current = 0;
      const perc = coveragePerc();
      onProgress({
        perc,
        seconds: Math.round(positionRef.current),
        completed: completed || perc >= COMPLETED_PERC,
        watchedSecondsDelta: delta,
        coverageBitmap: bucketsRef.current.join(""),
        coveragePerc: perc,
        lastPositionSeconds: Math.round(positionRef.current),
        playbackRate: rateRef.current
      });
    };

    // 1 segundo de vídeo só conta se está TOCANDO e a aba está VISÍVEL — vídeo
    // rodando em aba de fundo não é consumo (contraste com o podcast, que é
    // escuta legítima em segundo plano e por isso não tem este gate).
    const ticker = window.setInterval(() => {
      if (!playingRef.current || document.visibilityState === "hidden") return;
      unsyncedSecondsRef.current += 1;
      setWatched((value) => value + 1);
      markCurrentBucket();
      if (unsyncedSecondsRef.current >= SYNC_EVERY_SECONDS) sync();
    }, 1000);

    const onPlay = () => {
      playingRef.current = true;
      track("played", "resource", resourceId, { position_s: Math.round(positionRef.current) });
    };
    const onPause = () => {
      if (!playingRef.current) return;
      playingRef.current = false;
      track("paused", "resource", resourceId, { position_s: Math.round(positionRef.current) });
      sync();
    };
    const onEnded = () => {
      playingRef.current = false;
      track("completed", "resource", resourceId, { position_s: Math.round(positionRef.current) });
      sync(true);
    };
    const onSeek = (fromSeconds: number, toSeconds: number) => {
      track("seeked", "resource", resourceId, {
        from_s: Math.round(fromSeconds),
        to_s: Math.round(toSeconds)
      });
    };
    const onRate = (rate: number) => {
      if (rate === rateRef.current) return;
      rateRef.current = rate;
      track("rate_changed", "resource", resourceId, { rate });
    };

    let interval: number | undefined;
    let player: any;
    const slot = slotRef.current;
    if (!slot) return;

    if (ytId) {
      const target = document.createElement("div");
      slot.appendChild(target);
      loadYouTubeAPI().then((YT) => {
        player = new YT.Player(target, {
          videoId: ytId,
          width: "100%",
          events: {
            onReady: () => {
              // O polling é a única fonte de posição no YouTube (não há
              // timeupdate). Detecta seek comparando o salto com o esperado.
              interval = window.setInterval(() => {
                const duration = player.getDuration?.() ?? 0;
                const current = player.getCurrentTime?.() ?? 0;
                if (duration <= 0) return;
                durationRef.current = duration;
                const previous = positionRef.current;
                if (playingRef.current && Math.abs(current - previous) > 2) {
                  onSeek(previous, current);
                }
                positionRef.current = current;
                onRate(player.getPlaybackRate?.() ?? 1);
              }, 1000);
            },
            onStateChange: (event: { data: number }) => {
              const state = window.YT?.PlayerState;
              if (!state) return;
              if (event.data === state.PLAYING) onPlay();
              else if (event.data === state.PAUSED) onPause();
              else if (event.data === state.ENDED) onEnded();
            }
          }
        });
      });
    } else if (url) {
      const video = document.createElement("video");
      video.controls = true;
      video.src = url;
      video.className = "w-full rounded-[8px]";
      video.addEventListener("loadedmetadata", () => {
        durationRef.current = video.duration || 0;
      });
      video.addEventListener("timeupdate", () => {
        durationRef.current = video.duration || durationRef.current;
        positionRef.current = video.currentTime;
      });
      video.addEventListener("play", onPlay);
      video.addEventListener("pause", onPause);
      video.addEventListener("ended", onEnded);
      video.addEventListener("ratechange", () => onRate(video.playbackRate));
      // `seeking` dispara ANTES de currentTime saltar de fato na maioria dos
      // navegadores; guardamos a origem e comparamos no `seeked`.
      let seekFrom = 0;
      video.addEventListener("seeking", () => {
        seekFrom = positionRef.current;
      });
      video.addEventListener("seeked", () => {
        if (Math.abs(video.currentTime - seekFrom) > 1) onSeek(seekFrom, video.currentTime);
        positionRef.current = video.currentTime;
      });
      slot.appendChild(video);
    }

    // Não perder os últimos segundos ao fechar/ocultar a aba.
    const onPageHide = () => sync();
    const onVisibility = () => {
      if (document.visibilityState === "hidden") sync();
    };
    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      window.clearInterval(ticker);
      if (interval) window.clearInterval(interval);
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibility);
      sync(); // flush final ao trocar de vídeo/desmontar
      player?.destroy?.();
      if (slot) slot.innerHTML = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ytId, resourceId]);

  const minutes = Math.floor(watched / 60);
  const seconds = watched % 60;

  return (
    <div className="rounded-[8px] border border-line bg-white p-5">
      <h3 className="font-bold text-ink">{title}</h3>
      <div ref={slotRef} className="mt-3 aspect-video overflow-hidden rounded-[8px] bg-slate-950 [&>iframe]:h-full [&>iframe]:w-full" />
      <div className="mt-3 h-2 rounded-full bg-slate-100">
        <div className="h-2 rounded-full bg-brand transition-all" style={{ width: `${coverage}%` }} />
      </div>
      {/* O rótulo diz o que a barra REALMENTE mede: trecho do vídeo percorrido
          (não a posição alcançada). O tempo assistido aparece ao lado. */}
      <div className="mt-1 text-sm text-muted">
        {coverage}% {t("do vídeo assistido", "of the video watched")}
        {watched > 0 && (
          <> · {minutes}m{String(seconds).padStart(2, "0")}s {t("nesta sessão", "this session")}</>
        )}
      </div>
    </div>
  );
};
