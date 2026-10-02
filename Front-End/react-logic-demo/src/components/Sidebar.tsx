import { Award, BarChart3, Bell, BookOpen, CalendarDays, Grid2X2, Languages, LayoutDashboard, LogOut, Menu, MessageCircle, Search, Stars, TrendingUp, Users, X } from "lucide-react";
import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { StudentProfile } from "../services/api";
import { useLanguage, useT } from "../i18n";
import { useInterventions } from "../hooks/useInterventions";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { EduBotLogo } from "./brand/EduBotLogo";

interface NavItem {
  id: string;
  pt: string;
  en: string;
  icon: typeof Grid2X2;
}

interface SidebarProps {
  activeView: string;
  onChangeView: (view: string) => void;
  studentName: string;
  role: string;
  onLogout: () => void;
}

// Cada item guarda o rótulo nos dois idiomas (traduzido no render)
const navItems: NavItem[] = [
  { id: "dashboard", pt: "Dashboard", en: "Dashboard", icon: Grid2X2 },
  { id: "contents", pt: "Conteúdos", en: "Contents", icon: BookOpen },
  { id: "exercises", pt: "Atividades", en: "Activities", icon: CalendarDays },
  { id: "quiz", pt: "Quiz", en: "Quiz", icon: Award },
  { id: "reforco", pt: "Reforço", en: "Reinforcement", icon: Stars },
  { id: "evolution", pt: "Meu Desempenho", en: "My Performance", icon: BarChart3 },
  { id: "report", pt: "Professor Mediador", en: "Mediating Professor", icon: MessageCircle }
];

// Itens exclusivos de tutor/admin (gestão pedagógica)
const tutorItem: NavItem = { id: "tutor", pt: "Turma", en: "Class", icon: Users };
// Plano 5 (20.2): visão do gestor — "tudo que o sistema rastreia" da turma.
const gestorItem: NavItem = { id: "gestor", pt: "Visão do Gestor", en: "Manager View", icon: LayoutDashboard };

// O menu do STAFF (tutor/gestor) foca em gestão: NÃO herda as abas de aluno
// (Dashboard, Atividades, Quiz, Reforço, Meu Desempenho, Professor Mediador) —
// que são ferramentas de aprendizado e apareceriam vazias. Mantém só "Conteúdos"
// (para pré-visualizar o material do aluno) + Turma + Visão do Gestor.
export const STAFF_VIEWS = ["contents", "tutor", "gestor"];
const contentsItem = navItems.find((i) => i.id === "contents")!;

const itemsFor = (role: string): NavItem[] =>
  role === "tutor" || role === "admin" ? [contentsItem, tutorItem, gestorItem] : navItems;

// NA.1 (Plano 4): lista de navegação compartilhada entre a sidebar (desktop) e o
// drawer (mobile) — uma única fonte dos itens e do estilo. `aria-current="page"`
// marca a aba ativa para leitores de tela (NA.3 / A7).
const NavList = ({
  items,
  activeView,
  onNavigate
}: {
  items: NavItem[];
  activeView: string;
  onNavigate: (view: string) => void;
}) => {
  const t = useT();
  return (
    <>
      {items.map((item) => {
        const Icon = item.icon;
        const active = item.id === activeView;
        return (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            aria-current={active ? "page" : undefined}
            className={`flex h-14 w-full items-center gap-4 rounded-[8px] px-5 text-left text-lg transition ${
              active ? "bg-indigo-50 text-indigo-800 shadow-soft" : "text-muted hover:bg-slate-50"
            }`}
          >
            <Icon size={22} aria-hidden="true" />
            {t(item.pt, item.en)}
          </button>
        );
      })}
    </>
  );
};

export const Sidebar = ({ activeView, onChangeView, studentName, role, onLogout }: SidebarProps) => {
  const t = useT();
  const items = itemsFor(role);
  return (
    <aside className="hidden min-h-screen w-[340px] shrink-0 border-r border-line bg-white/70 lg:block">
      <div className="flex h-20 items-center gap-3 border-b border-line px-5">
        <EduBotLogo size={46} />
        <div>
          <div className="text-2xl font-bold leading-none text-ink">Adapta</div>
          <div className="mt-1 text-sm tracking-[0.18em] text-muted">LEARN · IA</div>
        </div>
      </div>

      <nav aria-label={t("Navegação principal", "Main navigation")} className="space-y-2 px-3 py-8">
        <NavList items={items} activeView={activeView} onNavigate={onChangeView} />
      </nav>

      {/* INTEGRAÇÃO (4.2): aluno logado real + logout */}
      <div className="mx-3 mt-auto border-t border-line px-2 py-6">
        <div className="px-3 text-sm text-muted">{t("Conectado como", "Signed in as")}</div>
        <div className="px-3 font-bold text-ink">{studentName}</div>
        <button
          onClick={onLogout}
          className="mt-3 flex h-11 w-full items-center gap-3 rounded-[8px] px-3 text-left text-muted transition hover:bg-rose-50 hover:text-rose-700"
        >
          <LogOut size={20} aria-hidden="true" />
          {t("Sair", "Sign out")}
        </button>
      </div>
    </aside>
  );
};

// NA.1 (Plano 4) — Navegação no celular. Hambúrguer (só < lg) que abre um drawer
// modal: role="dialog" + foco preso (useFocusTrap) + Esc/overlay fecham; escolher
// um item fecha o drawer e navega. Reaproveita o NavList (mesmos itens da sidebar).
export const MobileNav = ({ activeView, onChangeView, studentName, role, onLogout }: SidebarProps) => {
  const t = useT();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const items = itemsFor(role);

  useFocusTrap(panelRef, { active: open, onEscape: () => setOpen(false) });

  const navigate = (view: string) => {
    setOpen(false);
    onChangeView(view);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label={t("Abrir menu", "Open menu")}
        aria-expanded={open}
        aria-controls="mobile-nav"
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[8px] border border-line bg-white text-ink transition hover:bg-slate-50 lg:hidden"
      >
        <Menu size={22} aria-hidden="true" />
      </button>

      {/* Portal para o body: o header tem `backdrop-blur` (backdrop-filter), que
          criaria um bloco de contenção para o `position: fixed` — o drawer ficaria
          preso à altura do header. No body, o `fixed inset-0` cobre a viewport. */}
      {open && createPortal(
        <div className="fixed inset-0 z-50 lg:hidden">
          <style>{`
            @keyframes ebDrawerIn { from { transform: translateX(-100%); } to { transform: translateX(0); } }
            .eb-drawer-in { animation: ebDrawerIn .2s ease-out; }
            @media (prefers-reduced-motion: reduce) { .eb-drawer-in { animation: none !important; } }
          `}</style>
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            ref={panelRef}
            id="mobile-nav"
            role="dialog"
            aria-modal="true"
            aria-label={t("Menu", "Menu")}
            className="eb-drawer-in absolute inset-y-0 left-0 flex w-[300px] max-w-[85vw] flex-col border-r border-line bg-white shadow-soft"
          >
            <div className="flex h-20 items-center justify-between gap-3 border-b border-line px-5">
              <div className="flex items-center gap-3">
                <EduBotLogo size={40} />
                <div>
                  <div className="text-xl font-bold leading-none text-ink">Adapta</div>
                  <div className="mt-1 text-xs tracking-[0.18em] text-muted">LEARN · IA</div>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label={t("Fechar menu", "Close menu")}
                className="flex h-10 w-10 items-center justify-center rounded-[8px] text-muted transition hover:bg-slate-50"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>

            <nav aria-label={t("Navegação principal", "Main navigation")} className="flex-1 space-y-2 overflow-y-auto px-3 py-6">
              <NavList items={items} activeView={activeView} onNavigate={navigate} />
            </nav>

            <div className="border-t border-line px-5 py-5">
              <div className="text-sm text-muted">{t("Conectado como", "Signed in as")}</div>
              <div className="font-bold text-ink">{studentName}</div>
              <button
                onClick={onLogout}
                className="mt-3 flex h-11 w-full items-center gap-3 rounded-[8px] px-3 text-left text-muted transition hover:bg-rose-50 hover:text-rose-700"
              >
                <LogOut size={20} aria-hidden="true" />
                {t("Sair", "Sign out")}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

interface SearchResult {
  label: string;
  sub: string;
  view: string;
}

interface TopbarProps {
  profile: StudentProfile;
  onChangeView: (view: string) => void;
  // NA.1: a Topbar hospeda o hambúrguer/drawer (que precisa dos dados do aluno).
  activeView: string;
  studentName: string;
  role: string;
  onLogout: () => void;
}

// MELHORIA — a busca e o sino deixaram de ser decorativos:
//  - busca: filtra OVAs, competências e seções e navega para a aba certa;
//  - sino: abre os avisos do EduBot (histórico de intervenções) com badge.
// NA.2 (Plano 4): busca no padrão combobox (↑/↓/Enter/Esc + contagem anunciada) e
// sino operável por teclado (Esc fecha e devolve o foco; contagem no rótulo).
export const Topbar = ({ profile, onChangeView, activeView, studentName, role, onLogout }: TopbarProps) => {
  const t = useT();
  const { lang, toggle } = useLanguage();
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(-1);
  const [showNotif, setShowNotif] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const bellRef = useRef<HTMLButtonElement>(null);

  // Fecha os popovers ao clicar fora deles
  useEffect(() => {
    const onDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (searchRef.current && !searchRef.current.contains(target)) setQuery("");
      if (notifRef.current && !notifRef.current.contains(target)) setShowNotif(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const q = query.trim().toLowerCase();
  const staff = role === "tutor" || role === "admin";
  const results = useMemo<SearchResult[]>(() => {
    if (!q) return [];
    const out: SearchResult[] = [];
    // Só sugere seções que existem no menu do papel atual (staff não tem as abas
    // de aluno; sugerir "Meu Desempenho" para um gestor só levaria a um redirect).
    itemsFor(role).forEach((item) => {
      const label = t(item.pt, item.en);
      if (label.toLowerCase().includes(q)) out.push({ label, sub: t("Ir para a seção", "Go to section"), view: item.id });
    });
    profile.ovas.forEach((ova) => {
      if (ova.ova_name.toLowerCase().includes(q)) out.push({ label: ova.ova_name, sub: t("OVA · Conteúdos", "OVA · Contents"), view: "contents" });
    });
    // Competência → "Meu Desempenho" só faz sentido para o aluno.
    if (!staff) {
      profile.competencias.forEach((comp) => {
        if (comp.nome.toLowerCase().includes(q))
          out.push({ label: comp.nome, sub: t("Competência · Meu Desempenho", "Competency · My Performance"), view: "evolution" });
      });
    }
    return out.slice(0, 8);
  }, [q, profile, t, role, staff]);

  // A opção destacada zera quando os resultados mudam.
  useEffect(() => { setActiveIdx(-1); }, [q]);

  const pick = (view: string) => {
    onChangeView(view);
    setQuery("");
    setActiveIdx(-1);
  };

  const onSearchKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") { e.preventDefault(); setQuery(""); setActiveIdx(-1); return; }
    if (results.length === 0) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx((i) => (i + 1) % results.length); }
    // AUDITORIA P4: a fórmula anterior `(i - 1 + n) % n` com i=-1 (nenhuma seleção)
    // caía em n-2 em vez do último item (n-1) — confirmado ao vivo. `i <= 0` cobre
    // tanto "nada selecionado" quanto "no primeiro item", indo direto ao último.
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx((i) => (i <= 0 ? results.length - 1 : i - 1)); }
    else if (e.key === "Enter" && activeIdx >= 0) { e.preventDefault(); pick(results[activeIdx].view); }
  };

  // E.2 — sino lê a MESMA fonte do card do dashboard (não lidas) via hook único.
  const { items: notifications, dismiss } = useInterventions();
  const notifCount = notifications.length;

  const closeNotif = () => {
    setShowNotif(false);
    bellRef.current?.focus();
  };

  return (
    <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-line bg-slate-50/90 px-5 backdrop-blur">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {/* NA.1: hambúrguer + drawer (só aparece em telas < lg). */}
        <MobileNav
          activeView={activeView}
          onChangeView={onChangeView}
          studentName={studentName}
          role={role}
          onLogout={onLogout}
        />

        <div ref={searchRef} className="relative w-full max-w-[620px]">
          <div className="flex h-14 items-center gap-4 rounded-[8px] border border-line bg-slate-100 px-5 text-muted focus-within:border-brand">
            <Search size={24} aria-hidden="true" />
            <input
              role="combobox"
              aria-expanded={Boolean(q)}
              aria-controls="search-results"
              aria-activedescendant={activeIdx >= 0 ? `search-opt-${activeIdx}` : undefined}
              aria-autocomplete="list"
              aria-label={t("Buscar OVAs, competências, seções", "Search OVAs, competencies, sections")}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onSearchKeyDown}
              placeholder={t("Buscar OVAs, competências, seções...", "Search OVAs, competencies, sections...")}
              className="w-full bg-transparent text-lg text-ink outline-none placeholder:text-muted"
            />
          </div>
          {/* Contagem anunciada por leitor de tela (NA.2). */}
          <span className="sr-only" role="status">
            {q ? t(`${results.length} resultados`, `${results.length} results`) : ""}
          </span>
          {q && (
            <div
              id="search-results"
              role="listbox"
              aria-label={t("Resultados da busca", "Search results")}
              className="absolute left-0 right-0 top-16 z-30 overflow-hidden rounded-[8px] border border-line bg-white shadow-soft"
            >
              {results.length === 0 ? (
                <div className="px-5 py-4 text-muted">{t("Nada encontrado para", "No results for")} “{query}”.</div>
              ) : (
                results.map((result, index) => (
                  <button
                    key={`${result.view}-${index}`}
                    id={`search-opt-${index}`}
                    role="option"
                    aria-selected={index === activeIdx}
                    tabIndex={-1}
                    onClick={() => pick(result.view)}
                    onMouseEnter={() => setActiveIdx(index)}
                    className={`flex w-full flex-col items-start gap-0.5 border-b border-line px-5 py-3 text-left transition last:border-0 ${
                      index === activeIdx ? "bg-slate-50" : "hover:bg-slate-50"
                    }`}
                  >
                    <span className="font-semibold text-ink">{result.label}</span>
                    <span className="text-xs text-muted">{result.sub}</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      <div className="ml-4 flex items-center gap-4">
        {/* Alternador de idioma PT/EN */}
        <button
          onClick={toggle}
          className="flex h-10 items-center gap-2 rounded-[8px] border border-line bg-white px-3 font-bold text-ink transition hover:bg-slate-50"
          aria-label={t("Trocar idioma", "Switch language")}
          title={t("Trocar idioma", "Switch language")}
        >
          <Languages size={18} className="text-brand" aria-hidden="true" />
          {lang === "pt" ? "PT" : "EN"}
        </button>

        {/* INTEGRAÇÃO: o chip fake de "streak" virou o consumo real de recursos.
            NA.1: oculto em telas muito estreitas para o header não transbordar
            sobre o hambúrguer (o mesmo dado está no dashboard). */}
        <div className="hidden h-10 items-center gap-2 rounded-[8px] bg-coral px-4 font-bold text-white sm:flex">
          <TrendingUp size={19} aria-hidden="true" />
          {profile.recursos.percentual_consumido}% {t("consumido", "consumed")}
        </div>
        <div
          ref={notifRef}
          className="relative"
          onKeyDown={(e) => { if (e.key === "Escape" && showNotif) { e.preventDefault(); closeNotif(); } }}
        >
          <button
            ref={bellRef}
            onClick={() => setShowNotif((value) => !value)}
            aria-expanded={showNotif}
            aria-controls="notif-popover"
            className="relative flex h-12 w-12 items-center justify-center rounded-full border border-line bg-white text-ink transition hover:bg-slate-50"
            aria-label={
              notifCount > 0
                ? t(`Avisos do EduBot — ${notifCount} não lidos`, `EduBot notices — ${notifCount} unread`)
                : t("Avisos do EduBot", "EduBot notices")
            }
          >
            <Bell size={22} aria-hidden="true" />
            {notifCount > 0 && <span className="absolute right-3 top-3 h-2.5 w-2.5 rounded-full bg-red-500" aria-hidden="true" />}
          </button>
          {showNotif && (
            <div id="notif-popover" className="absolute right-0 top-14 z-30 w-80 overflow-hidden rounded-[8px] border border-line bg-white shadow-soft">
              <div className="border-b border-line px-4 py-3 font-bold text-ink">{t("Avisos do EduBot", "EduBot notices")}</div>
              <div className="max-h-96 overflow-auto">
                {notifications.length === 0 ? (
                  <p className="px-4 py-4 text-sm text-muted">{t("Nenhum aviso por enquanto.", "No notices yet.")}</p>
                ) : (
                  notifications.map((item) => (
                    <div key={item.intervention_id} className="border-b border-line px-4 py-3 last:border-0">
                      <div className="flex items-center justify-between text-xs text-muted">
                        <span className="font-bold uppercase tracking-wide">{item.tipo}</span>
                        <button
                          onClick={() => dismiss(item.intervention_id)}
                          className="text-muted transition hover:text-ink"
                          aria-label={t(`Dispensar aviso: ${item.tipo}`, `Dismiss notice: ${item.tipo}`)}
                        >
                          <X size={14} aria-hidden="true" />
                        </button>
                      </div>
                      {item.descricao && <p className="mt-1 text-sm text-slate-700">{item.descricao}</p>}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
