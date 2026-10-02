/*
Leitura por SEÇÃO do OVA (Plano de Rastreabilidade — Fase 2).

Fecha a lacuna central da auditoria (P5): o rastreio media o OVA inteiro, então
o professor via QUANTO o aluno leu, nunca ONDE ele travou.

Duas decisões de projeto importantes:

1. NÃO existe um segundo cronômetro. O leitor já tem um ticker de 1 s com o gate
   honesto de leitura (só conta com a aba visível e o aluno ativo). Este hook
   expõe `creditSecond()`, que aquele ticker chama — assim o tempo por seção usa
   exatamente o mesmo critério do tempo total, e a invariante
   "soma das seções <= total do OVA" se sustenta.

2. Quando duas seções estão visíveis ao mesmo tempo (tela grande), o segundo é
   dividido entre elas em vez de contado duas vezes — senão a soma das partes
   ultrapassaria o todo. Os restos fracionários ficam pendentes e entram no
   próximo envio, sem perder tempo por arredondamento.
*/
import { useCallback, useEffect, useRef } from "react";
import { SectionProgressInput, saveSectionProgress } from "../services/api";
import { track } from "../services/events";

// Metade da seção visível já caracteriza leitura daquela parte.
const VISIBILITY_THRESHOLD = 0.5;
// Uma seção precisa ficar visível por este tempo para contar como "entrou" —
// rolagem rápida atravessando a tela não é leitura.
const MIN_DWELL_MS = 1000;

interface SectionState {
  index: number;
  pendingSeconds: number;   // fração acumulada ainda não enviada
  pendingVisits: number;
  maxScrollPerc: number;
  visibleSince: number | null;
  counted: boolean;         // já passou do MIN_DWELL_MS nesta visita
  activeSecondsInVisit: number;
}

export function useSectionTracking(ovaId: number) {
  const statesRef = useRef<Map<string, SectionState>>(new Map());
  const elementsRef = useRef<Map<string, Element>>(new Map());
  const observerRef = useRef<IntersectionObserver | null>(null);

  // Troca de OVA: o histórico de seções do anterior não pode vazar para o novo.
  useEffect(() => {
    statesRef.current = new Map();
    elementsRef.current = new Map();
  }, [ovaId]);

  const stateFor = (sectionId: string, index: number): SectionState => {
    const existing = statesRef.current.get(sectionId);
    if (existing) return existing;
    const created: SectionState = {
      index,
      pendingSeconds: 0,
      pendingVisits: 0,
      maxScrollPerc: 0,
      visibleSince: null,
      counted: false,
      activeSecondsInVisit: 0
    };
    statesRef.current.set(sectionId, created);
    return created;
  };

  /** Quanto da seção já passou pela viewport (marca d'água de leitura). */
  const scrollPercOf = (element: Element): number => {
    const rect = element.getBoundingClientRect();
    if (rect.height <= 0) return 0;
    const seen = window.innerHeight - rect.top;
    return Math.max(0, Math.min(100, Math.round((seen / rect.height) * 100)));
  };

  const observer = (): IntersectionObserver => {
    if (observerRef.current) return observerRef.current;
    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const sectionId = (entry.target as HTMLElement).dataset.sectionId;
          if (!sectionId) continue;
          const state = statesRef.current.get(sectionId);
          if (!state) continue;

          if (entry.isIntersecting) {
            state.visibleSince = Date.now();
            state.activeSecondsInVisit = 0;
          } else if (state.visibleSince !== null) {
            // Saída: só vira visita/evento se a permanência foi real.
            if (state.counted) {
              track("section_exit", "ova_section", ovaId, {
                section_id: sectionId,
                section_index: state.index,
                active_seconds: Math.round(state.activeSecondsInVisit),
                max_scroll_perc: state.maxScrollPerc
              });
            }
            state.visibleSince = null;
            state.counted = false;
          }
        }
      },
      { threshold: VISIBILITY_THRESHOLD }
    );
    return observerRef.current;
  };

  /**
   * Ref callback para o elemento da seção. Registra no observer e guarda a
   * identidade da seção no próprio nó (dataset), que é o que o observer lê.
   */
  const observeSection = useCallback(
    (sectionId: string, index: number) => (element: HTMLElement | null) => {
      const previous = elementsRef.current.get(sectionId);
      if (previous && previous !== element) observer().unobserve(previous);
      if (!element) {
        elementsRef.current.delete(sectionId);
        return;
      }
      element.dataset.sectionId = sectionId;
      stateFor(sectionId, index).index = index;
      elementsRef.current.set(sectionId, element);
      observer().observe(element);
    },
    // `ovaId` entra porque os eventos emitidos carregam o OVA corrente.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ovaId]
  );

  /**
   * Credita UM segundo de leitura ativa às seções visíveis. Chamado pelo ticker
   * do leitor — que já aplicou o gate de visibilidade/ociosidade.
   */
  const creditSecond = useCallback(() => {
    const now = Date.now();
    const visible: [string, SectionState][] = [];
    statesRef.current.forEach((state, sectionId) => {
      if (state.visibleSince !== null && now - state.visibleSince >= MIN_DWELL_MS) {
        visible.push([sectionId, state]);
      }
    });
    if (visible.length === 0) return;

    const share = 1 / visible.length; // não contar o mesmo segundo duas vezes
    for (const [sectionId, state] of visible) {
      if (!state.counted) {
        // Primeira vez que esta visita conta: é uma entrada de fato.
        state.counted = true;
        state.pendingVisits += 1;
        track("section_enter", "ova_section", ovaId, {
          section_id: sectionId,
          section_index: state.index
        });
      }
      state.pendingSeconds += share;
      state.activeSecondsInVisit += share;
      const element = elementsRef.current.get(sectionId);
      if (element) state.maxScrollPerc = Math.max(state.maxScrollPerc, scrollPercOf(element));
    }
  }, [ovaId]);

  /**
   * Envia os deltas acumulados. Só manda seções com algo a reportar; os restos
   * fracionários de segundo permanecem pendentes para o próximo envio.
   */
  const flushSections = useCallback(
    (keepalive = false) => {
      const payload: SectionProgressInput[] = [];
      statesRef.current.forEach((state, sectionId) => {
        const wholeSeconds = Math.floor(state.pendingSeconds);
        if (wholeSeconds <= 0 && state.pendingVisits === 0) return;
        payload.push({
          section_id: sectionId,
          section_index: state.index,
          seconds_delta: wholeSeconds,
          max_scroll_perc: state.maxScrollPerc,
          visits_delta: state.pendingVisits
        });
        state.pendingSeconds -= wholeSeconds;
        state.pendingVisits = 0;
      });
      if (payload.length === 0) return;
      saveSectionProgress(ovaId, payload, { keepalive }).catch(() => {
        // Best-effort, como o resto do rastreio: devolve o que não foi aceito
        // para a próxima janela de sync (exceto no flush final de unload).
        if (keepalive) return;
        for (const item of payload) {
          const state = statesRef.current.get(item.section_id);
          if (!state) continue;
          state.pendingSeconds += item.seconds_delta;
          state.pendingVisits += item.visits_delta;
        }
      });
    },
    [ovaId]
  );

  useEffect(() => {
    return () => {
      observerRef.current?.disconnect();
      observerRef.current = null;
    };
  }, []);

  return { observeSection, creditSecond, flushSections };
}
