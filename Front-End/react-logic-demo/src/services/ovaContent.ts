/*
MELHORIA (Migração do OVA para o front novo) — Carregamento e parsing do
conteúdo do OVA.

O conteúdo de cada OVA continua sendo o HTML estático servido pelo Apache em
`/html/ovas/<link>` (fonte única de verdade). Em vez de exibi-lo no leitor
legado (iframe + Bootstrap/jQuery), buscamos o HTML em runtime e o convertemos
em um MODELO ESTRUTURADO (seções, parágrafos, imagens, carrosséis e acordeões)
que o OvaReader renderiza NATIVAMENTE com o design system do dashboard.

O mesmo texto extraído (ovaContextText) é enviado ao Tutor IA como contexto, de
modo que o tutor responde estritamente sobre o conteúdo que o aluno consumiu.
*/
import { CLASSIC_BASE_URL } from "./config";
import { Lang } from "../i18n";

export interface CarouselItem {
  title?: string;
  image?: string;
  text: string;
}

export type OvaBlock =
  | { kind: "paragraph"; text: string }
  | { kind: "image"; src: string; alt?: string }
  | { kind: "carousel"; items: CarouselItem[] }
  | { kind: "accordion"; items: { title: string; body: string }[] };

export interface OvaSection {
  id: string;
  heading: string | null;
  blocks: OvaBlock[];
  hasQuiz: boolean;
}

export interface OvaContent {
  title: string;
  heroLabel: string | null;
  intro: string | null;
  sections: OvaSection[];
}

// As imagens dos OVAs são referenciadas como "../../imagens/x.png" (relativo ao
// leitor legado). O Apache as serve em /imagens/x.png — reescrevemos para a URL
// absoluta para que carreguem tanto no app (8010/app) quanto no dev (5173).
const rewriteImg = (src: string): string => {
  const marker = "imagens/";
  const idx = src.indexOf(marker);
  const file = idx >= 0 ? src.slice(idx + marker.length) : src.replace(/^.*\//, "");
  return `${CLASSIC_BASE_URL}/imagens/${file}`;
};

const text = (el: Element | null | undefined): string => (el?.textContent ?? "").trim();

const parseCarousel = (el: Element): OvaBlock => {
  const items: CarouselItem[] = [];
  const parts = el.querySelector(".parts");
  if (parts) {
    Array.from(parts.children).forEach((part) => {
      const img = part.querySelector("img");
      items.push({
        title: text(part.querySelector("h2")) || undefined,
        image: img ? rewriteImg(img.getAttribute("src") ?? "") : undefined,
        text: text(part.querySelector("p"))
      });
    });
  }
  return { kind: "carousel", items };
};

const parseAccordion = (el: Element): OvaBlock => {
  const items: { title: string; body: string }[] = [];
  el.querySelectorAll(".accordion-item").forEach((item) => {
    items.push({
      title: text(item.querySelector(".accordion-button")),
      body: text(item.querySelector(".accordion-body"))
    });
  });
  return { kind: "accordion", items };
};

// Percorre o DOM da seção emitindo blocos. Carrossel e acordeão são tratados
// como unidades (não recursamos dentro deles); parágrafos e imagens soltos
// viram blocos; qualquer outro contêiner é percorrido recursivamente.
const walk = (node: Element, blocks: OvaBlock[]) => {
  Array.from(node.children).forEach((child) => {
    if (child.classList.contains("carrousel")) {
      blocks.push(parseCarousel(child));
    } else if (child.classList.contains("accordion")) {
      blocks.push(parseAccordion(child));
    } else if (child.tagName === "IMG") {
      blocks.push({
        kind: "image",
        src: rewriteImg(child.getAttribute("src") ?? ""),
        alt: child.getAttribute("alt") ?? undefined
      });
    } else if (child.tagName === "P") {
      const value = text(child);
      if (value) blocks.push({ kind: "paragraph", text: value });
    } else {
      walk(child, blocks);
    }
  });
};

const parseDocument = (html: string, fallbackTitle: string): OvaContent => {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const sections: OvaSection[] = [];
  let heroLabel: string | null = null;
  let intro: string | null = null;

  Array.from(doc.body.children).forEach((section) => {
    if (section.tagName !== "SECTION") return;
    const id = section.id || "";

    if (id === "introduction") {
      const paragraphs = Array.from(section.querySelectorAll("p"))
        .map((p) => text(p))
        .filter(Boolean);
      heroLabel = paragraphs[0] ?? null;
      intro = paragraphs[1] ?? paragraphs[0] ?? null;
      return;
    }
    // A seção "resources" é dinâmica (vídeos/podcasts/atividades do banco) e é
    // renderizada à parte pelo OvaReader via getOVAResources.
    if (id === "resources") return;

    const container = section.querySelector(".container") ?? section;
    const blocks: OvaBlock[] = [];
    walk(container, blocks);

    sections.push({
      id,
      heading: text(section.querySelector("h1")) || null,
      blocks,
      hasQuiz: !!section.querySelector(".questions")
    });
  });

  return { title: fallbackTitle, heroLabel, intro, sections };
};

export async function fetchOvaContent(link: string, fallbackTitle: string, lang: Lang = "pt"): Promise<OvaContent> {
  const base = `${CLASSIC_BASE_URL}/html/ovas/`;
  // No modo inglês, tenta a variante "<arquivo>.en.html"; se ela não existir,
  // cai no HTML original (PT). Assim traduzimos só os OVAs que têm versão EN.
  if (lang === "en") {
    const enLink = link.replace(/\.html$/i, ".en.html");
    try {
      const enResp = await fetch(`${base}${enLink}`);
      if (enResp.ok) return parseDocument(await enResp.text(), fallbackTitle);
    } catch {
      /* rede/404 — usa o original abaixo */
    }
  }
  const response = await fetch(`${base}${link}`);
  if (!response.ok) throw new Error(`Não foi possível carregar o conteúdo do OVA (${response.status}).`);
  return parseDocument(await response.text(), fallbackTitle);
}

// Serializa o conteúdo do OVA no formato que o Tutor IA espera como contexto:
//   # <título>
//   ## <seção>
//   <parágrafo / item de carrossel / item de acordeão>
export function ovaContextText(content: OvaContent): string {
  const lines: string[] = [`# ${content.title}`];
  if (content.intro) {
    lines.push("## Introdução", content.intro);
  }
  content.sections.forEach((section) => {
    lines.push(`## ${section.heading ?? section.id}`);
    section.blocks.forEach((block) => {
      if (block.kind === "paragraph") {
        lines.push(block.text);
      } else if (block.kind === "carousel") {
        block.items.forEach((item) =>
          lines.push(item.title ? `${item.title}: ${item.text}` : item.text)
        );
      } else if (block.kind === "accordion") {
        block.items.forEach((item) => lines.push(`${item.title}: ${item.body}`));
      }
    });
  });
  return lines.join("\n");
}
