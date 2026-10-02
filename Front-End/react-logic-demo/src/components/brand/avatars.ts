/*
MELHORIA (Roteiro Cena 3) — Personas 3D do EduBot (100% offline, Three.js).

Cada persona é um personagem 3D construído em código (sem baixar nenhum arquivo,
sem depender de site externo). O aluno escolhe entre elas no card "Meu
Desempenho". A boca anima enquanto o EduBot fala.

Para criar uma nova persona: adicione um item aqui (variante + paleta) e, se for
um novo "tipo" de cabeça, trate a `variant` em Avatar3D.tsx.
*/
import type { Lang } from "../../i18n";

export type AvatarVariant = "einstein" | "curie";

export interface AvatarPalette {
  skin: string;
  hair: string;
  cloth: string;
  accent: string;
}

export interface AvatarPersona {
  id: string;
  variant: AvatarVariant;
  /** Nome exibido no seletor e no balão. */
  name: { pt: string; en: string };
  /** Legenda curta (área de atuação do cientista). */
  tagline: { pt: string; en: string };
  palette: AvatarPalette;
  /** Cor de fundo do canvas (combina com o card). */
  bg?: string;
}

export const AVATAR_PERSONAS: AvatarPersona[] = [
  {
    id: "einstein",
    variant: "einstein",
    name: { pt: "Prof. Einstein", en: "Prof. Einstein" },
    tagline: { pt: "Física & relatividade", en: "Physics & relativity" },
    palette: { skin: "#e8c4a0", hair: "#e6e6ea", cloth: "#4b4f63", accent: "#2b2b33" },
    bg: "#eef0fb"
  },
  {
    id: "curie",
    variant: "curie",
    name: { pt: "Dra. Marie Curie", en: "Dr. Marie Curie" },
    tagline: { pt: "Química & radioatividade", en: "Chemistry & radioactivity" },
    palette: { skin: "#eccdb4", hair: "#3a2b24", cloth: "#3a3550", accent: "#1f1b2e" },
    bg: "#fdeeec"
  }
];

export function personaName(p: AvatarPersona, lang: Lang): string {
  return lang === "en" ? p.name.en : p.name.pt;
}

export function personaTagline(p: AvatarPersona, lang: Lang): string {
  return lang === "en" ? p.tagline.en : p.tagline.pt;
}
