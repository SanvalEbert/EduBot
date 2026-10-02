/*
MELHORIA — Internacionalização (PT/EN).

Abordagem enxuta e à prova de erro de chave: em vez de um dicionário com chaves,
cada texto é escrito nos dois idiomas na hora do uso — `t("Olá", "Hello")`. O
idioma atual vem do contexto e é lembrado no localStorage. Um alternador PT/EN
na Topbar troca em tempo real. O conteúdo dos OVAs (HTML) permanece no idioma
original — aqui traduzimos a INTERFACE.
*/
import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { safeGet, safeSet } from "./services/storage";

export type Lang = "pt" | "en";

interface LanguageContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  toggle: () => void;
  // t(pt, en) devolve o texto no idioma atual
  t: (pt: string, en: string) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);
const STORAGE_KEY = "edubot.lang";

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = safeGet("local", STORAGE_KEY);
    return saved === "en" || saved === "pt" ? saved : "pt";
  });

  const setLang = useCallback((next: Lang) => {
    safeSet("local", STORAGE_KEY, next);
    setLangState(next);
  }, []);

  // AC.4 (Plano 4): mantém <html lang> em sincronia com o idioma da UI — leitores
  // de tela trocam a pronúncia (WCAG 3.1.1/3.1.2). Roda no mount (cobre quem já
  // carrega em EN pelo localStorage) e a cada troca.
  useEffect(() => {
    document.documentElement.lang = lang === "en" ? "en" : "pt-BR";
  }, [lang]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      lang,
      setLang,
      toggle: () => setLang(lang === "pt" ? "en" : "pt"),
      t: (pt: string, en: string) => (lang === "en" ? en : pt)
    }),
    [lang, setLang]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
};

export const useLanguage = (): LanguageContextValue => {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage precisa estar dentro de <LanguageProvider>");
  return ctx;
};

// Atalho: hook que devolve apenas a função de tradução
export const useT = () => useLanguage().t;
