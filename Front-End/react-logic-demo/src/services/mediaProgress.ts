/*
Progresso de mídia — contrato entre os players e a API (Plano de Rastreabilidade,
Fase 1).

Os três lugares que exibem mídia (leitor de OVA, Conteúdos e Reforço) mandavam o
mesmo payload copiado à mão. Com a Fase 1 o payload cresceu (tempo assistido real,
bitmap de cobertura, posição, velocidade) e a cópia triplicada viraria três
oportunidades de esquecer um campo — que é exatamente como uma métrica volta a
mentir. O mapeamento mora aqui, em um lugar só.
*/
import { saveResourceProgress } from "./api";

export interface MediaProgress {
  perc: number;
  seconds: number;
  completed: boolean;
  // Campos do consumo REAL — só o player de vídeo os mede; o de áudio já reporta
  // tempo de escuta honesto em `seconds` e os deixa indefinidos.
  watchedSecondsDelta?: number;
  coverageBitmap?: string;
  coveragePerc?: number;
  lastPositionSeconds?: number;
  playbackRate?: number;
}

export const saveMediaProgress = (
  resourceId: number,
  state: Partial<MediaProgress>,
  opts: { keepalive?: boolean } = {}
) =>
  saveResourceProgress(
    {
      resource_id: resourceId,
      perc_consumed: state.perc ?? 0,
      seconds_consumed: state.seconds ?? 0,
      completed: state.completed ?? false,
      watched_seconds_delta: state.watchedSecondsDelta,
      coverage_bitmap: state.coverageBitmap,
      last_position_s: state.lastPositionSeconds,
      playback_rate: state.playbackRate
    },
    opts
  );
