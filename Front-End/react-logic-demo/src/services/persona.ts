/*
AV.2 (Plano 3) — persona do companheiro de estudo, agora PERSISTIDA no servidor.

Antes (V.2) a escolha vivia só em localStorage: não seguia o aluno entre
dispositivos e o backend não sabia qual persona "fala" (o tutor IA não conseguia
ser o Einstein). Agora a fonte da verdade é `students.persona` (GET /student/me);
o localStorage é só um CACHE para a tela de login (antes do perfil carregar) e
para uma UI instantânea ao trocar.
*/
import { setStudentPersona } from "./api";
import { safeGet, safeSet } from "./storage";

const PERSONA_KEY = "edubot.persona";

export const VALID_PERSONAS = ["edubot", "einstein", "curie"] as const;

/** Persona corrente do cache local (fallback 'edubot'). Use o perfil como fonte
 * da verdade quando ele já estiver carregado. */
export const getPersona = (): string => safeGet("local", PERSONA_KEY) || "edubot";

/** Alinha o cache local à persona vinda do servidor (chamar quando o perfil carrega). */
export const syncPersonaFromProfile = (persona?: string | null) => {
  if (persona) safeSet("local", PERSONA_KEY, persona);
};

/** Grava a escolha: cache local imediato (UI responsiva) + persiste no servidor
 * (fire-and-forget — um erro de rede não bloqueia a troca visual). */
export const setPersona = (id: string) => {
  safeSet("local", PERSONA_KEY, id);
  setStudentPersona(id).catch(() => undefined);
};
