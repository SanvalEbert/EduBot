/*
INTEGRAÇÃO (EduBot Track) — o app deixou de ser um demo isolado em localStorage
e passou a consumir o backend Flask:
  - Sem token -> tela de Login (POST /login)
  - Logado    -> perfil real via GET /student/me alimenta todas as views
O visual original (Lovable) foi mantido; apenas a fonte dos dados mudou.
*/
import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { Sidebar, STAFF_VIEWS, Topbar } from "./components/Sidebar";
import { Login } from "./components/Login";
import { ConsentModal, CONSENT_FLAG } from "./components/ConsentModal";
import { OnboardingModal, ONBOARDING_FLAG } from "./components/OnboardingModal";
import { LoaderCircle } from "lucide-react";
import { OvaState, Session, StudentProfile, clearSession, getMe, getSession, getToken, hasRecordedConsent } from "./services/api";
import { syncPersonaFromProfile } from "./services/persona";
import { useLanguage, useT } from "./i18n";
import { safeGet, safeSet, safeRemove } from "./services/storage";

// MELHORIA — cada tela vira um chunk separado (React.lazy), então o app só baixa
// o código da aba que o aluno abrir, em vez de tudo (inclusive os gráficos
// pesados do Recharts) no primeiro carregamento.
const Dashboard = lazy(() => import("./components/Dashboard").then((m) => ({ default: m.Dashboard })));
const Contents = lazy(() => import("./components/Contents").then((m) => ({ default: m.Contents })));
const Evolution = lazy(() => import("./components/Evolution").then((m) => ({ default: m.Evolution })));
const Exercises = lazy(() => import("./components/Exercises").then((m) => ({ default: m.Exercises })));
const Quiz = lazy(() => import("./components/Quiz").then((m) => ({ default: m.Quiz })));
const Reforco = lazy(() => import("./components/Reforco").then((m) => ({ default: m.Reforco })));
const Report = lazy(() => import("./components/Report").then((m) => ({ default: m.Report })));
const OvaReader = lazy(() => import("./components/ova/OvaReader").then((m) => ({ default: m.OvaReader })));
const TutorPanel = lazy(() => import("./components/TutorPanel").then((m) => ({ default: m.TutorPanel })));
// Plano 5: detalhe do aluno visto pelo professor (#/aluno/:id) e painel do gestor.
const TutorStudentDetail = lazy(() => import("./components/TutorStudentDetail").then((m) => ({ default: m.TutorStudentDetail })));
const ManagerDashboard = lazy(() => import("./components/ManagerDashboard").then((m) => ({ default: m.ManagerDashboard })));

const ViewFallback = () => {
  const t = useT();
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <LoaderCircle className="animate-spin text-brand" size={32} aria-hidden="true" />
      {/* VI.2: com reduced-motion o spinner congela — o texto sr-only mantém o sentido. */}
      <span className="sr-only">{t("Carregando", "Loading")}</span>
    </div>
  );
};

// Fase 5 (A17): URLs navegáveis por hash (#/dashboard, #/quiz...). HashRouting
// dispensa reescrita no Apache (o app é servido em subpath /app/) e dá botão
// voltar/avançar + links compartilháveis. As views válidas espelham a Sidebar.
// E.1 (Plano 2): `#/modulo/:id` abre o leitor daquele OVA — módulos viram
// deep-linkáveis (F5 reabre o mesmo módulo; uma intervenção pode apontar o alvo).
// Plano 5: "gestor" (dashboard do gestor) entra como view conhecida (staff).
const KNOWN_VIEWS = ["dashboard", "contents", "exercises", "quiz", "reforco", "evolution", "report", "tutor", "gestor"];
const parseHash = (): { view: string; ovaId?: number; studentId?: number } => {
  const m = window.location.hash.match(/^#\/modulo\/(\d+)/);
  if (m) return { view: "module", ovaId: Number(m[1]) };
  // Plano 5 (19.2): #/aluno/:id abre o detalhe daquele aluno para o professor.
  const a = window.location.hash.match(/^#\/aluno\/(\d+)/);
  if (a) return { view: "aluno", studentId: Number(a[1]) };
  const raw = window.location.hash.replace(/^#\/?/, "");
  return { view: KNOWN_VIEWS.includes(raw) ? raw : "dashboard" };
};

const App = () => {
  const initialHash = parseHash();
  const [activeView, setActiveView] = useState<string>(() =>
    initialHash.view === "module" ? "contents"
      : initialHash.view === "aluno" ? "tutor"  // Plano 5: detalhe do aluno mora "dentro" da Turma
      : initialHash.view);
  // Plano 5 (19.2): id do aluno aberto no detalhe do professor (null = nenhum).
  const [tutorStudentId, setTutorStudentId] = useState<number | null>(initialHash.studentId ?? null);
  const [session, setSession] = useState<Session | null>(() => (getToken() ? getSession() : null));
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  // OVA aberto no leitor nativo (null = nenhum). Tem precedência sobre activeView.
  const [readerOva, setReaderOva] = useState<OvaState | null>(null);
  // E.1: id do módulo pedido pela URL (#/modulo/:id); resolvido para readerOva
  // quando o perfil carrega (o OVA vem de profile.ovas).
  const [moduleId, setModuleId] = useState<number | null>(initialHash.ovaId ?? null);
  // D.5: modal de consentimento no primeiro login (flag em localStorage).
  const [needsConsent, setNeedsConsent] = useState<boolean>(
    () => safeGet("local", CONSENT_FLAG) !== "1"
  );
  // U.5: onboarding logo após o consentimento (outra flag em localStorage).
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean>(
    () => safeGet("local", ONBOARDING_FLAG) !== "1"
  );
  const t = useT();
  const { lang } = useLanguage();

  // (Re)carrega o perfil completo do aluno — chamado no login e após cada
  // ação rastreada (progresso de mídia, quiz, recomendação), mantendo
  // dashboard/competências sempre coerentes com o backend
  const refreshProfile = useCallback(async () => {
    try {
      const me = await getMe();
      setProfile(me);
      // AV.2 (Plano 3): alinha o cache local da persona à fonte da verdade (servidor),
      // para os pontos que a leem antes do perfil (ex.: companheiro no OVA).
      syncPersonaFromProfile(me.estudante.persona);
      setError(null);
    } catch (err) {
      // Token inválido/expirado -> volta para o login
      if ((err as { status?: number }).status === 401) {
        setSession(null);
        setProfile(null);
      } else {
        setError("load_failed");
      }
    }
  }, []);

  // Recarrega também quando o idioma muda: o conteúdo (nomes de OVA, recursos,
  // competências) vem TRADUZIDO do banco conforme ?lang= (Fase 4 — A12).
  useEffect(() => {
    if (session) refreshProfile();
  }, [session, refreshProfile, lang]);

  // Fase 0 (E0.5) do Plano de Rastreabilidade: a flag local é só cache — quem
  // manda é o backend. Ao autenticar, conferimos se existe consentimento
  // GRAVADO: se não existe (navegador novo, POST que falhou), o modal volta;
  // se existe, gravamos o cache para não piscar o modal nas próximas visitas.
  // Best-effort: se a consulta falhar, mantém o comportamento do cache.
  useEffect(() => {
    if (!session) return;
    let active = true;
    hasRecordedConsent()
      .then((recorded) => {
        if (!active) return;
        if (recorded) safeSet("local", CONSENT_FLAG, "1");
        else safeRemove("local", CONSENT_FLAG);
        setNeedsConsent(!recorded);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [session]);

  const logout = () => {
    clearSession();
    setSession(null);
    setProfile(null);
    setReaderOva(null);
    setActiveView("dashboard");
    window.location.hash = "#/dashboard";
  };

  // Troca de aba pela sidebar/topbar: fecha o leitor de OVA e reflete na URL
  // (hash). Fecha o leitor diretamente para cobrir o caso de reabrir a mesma
  // aba onde o OVA estava aberto (o hash não mudaria e não dispararia o evento).
  const changeView = useCallback((view: string) => {
    setReaderOva(null);
    setModuleId(null);
    setTutorStudentId(null); // Plano 5: sair do detalhe de aluno ao trocar de aba
    setActiveView(view);
    if (window.location.hash !== `#/${view}`) window.location.hash = `#/${view}`;
  }, []);

  // Sincroniza com o botão voltar/avançar do navegador. `#/modulo/:id` mantém o
  // moduleId (o leitor é reaberto pelo efeito); as demais views fecham o leitor.
  useEffect(() => {
    const onHashChange = () => {
      const p = parseHash();
      if (p.view === "module" && p.ovaId != null) {
        setModuleId(p.ovaId);
        setTutorStudentId(null);
      } else if (p.view === "aluno" && p.studentId != null) {
        // Plano 5: detalhe do aluno tem precedência; a aba de fundo é a Turma.
        setTutorStudentId(p.studentId);
        setModuleId(null);
        setReaderOva(null);
        setActiveView("tutor");
      } else {
        setModuleId(null);
        setReaderOva(null);
        setTutorStudentId(null);
        setActiveView(p.view);
      }
    };
    window.addEventListener("hashchange", onHashChange);
    if (!window.location.hash) {
      window.history.replaceState(null, "", `#/${parseHash().view}`);
    }
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // E.1: resolve o módulo pedido pela URL para o leitor, assim que o perfil
  // (profile.ovas) estiver disponível — F5 dentro de um módulo reabre o mesmo.
  useEffect(() => {
    if (moduleId != null && profile) {
      const ova = profile.ovas.find((o) => o.ova_id === moduleId);
      if (ova) setReaderOva(ova);
    }
  }, [moduleId, profile]);

  // Papel do usuário (staff = tutor/admin). Deriva do perfil carregado.
  const isStaff = profile?.estudante.role === "tutor" || profile?.estudante.role === "admin";

  // O staff não usa as abas de aluno: se cair numa delas (default de login ou URL
  // digitada à mão), manda para a Turma. O aluno, por sua vez, não acessa
  // Turma/Gestor. O detalhe de aluno e o leitor de OVA têm precedência (não mexe).
  useEffect(() => {
    if (!profile || tutorStudentId != null || readerOva) return;
    if (isStaff) {
      if (!STAFF_VIEWS.includes(activeView)) changeView("tutor");
    } else if (activeView === "tutor" || activeView === "gestor") {
      changeView("dashboard");
    }
  }, [profile, isStaff, activeView, tutorStudentId, readerOva, changeView]);

  // Abre um OVA no leitor nativo (chamado pela Área de Conteúdo). Reflete a URL
  // em #/modulo/:id (deep-link) — F5/voltar funcionam dentro do módulo.
  const openOva = (ova: OvaState) => {
    setReaderOva(ova);
    setModuleId(ova.ova_id);
    if (window.location.hash !== `#/modulo/${ova.ova_id}`) {
      window.location.hash = `#/modulo/${ova.ova_id}`;
    }
    window.scrollTo({ top: 0 });
  };

  // Fecha o leitor voltando para "Conteúdos" (limpa o #/modulo da URL).
  const closeReader = () => changeView("contents");

  if (!session) {
    return <Login onLogged={(logged) => setSession(logged)} />;
  }

  if (!profile) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 text-muted">
        <LoaderCircle className="animate-spin text-brand" size={40} />
        {error ? (
          <p className="font-semibold text-rose-600">
            {t("Não foi possível carregar seus dados. A API está no ar?", "Couldn't load your data. Is the API up?")}
          </p>
        ) : (
          <p>{t("Carregando seu perfil...", "Loading your profile...")}</p>
        )}
      </div>
    );
  }

  const renderView = () => {
    // Plano 5: detalhe do aluno (professor) tem precedência sobre a aba. Guarda
    // por papel — o backend também valida (404 fora de escopo), mas o front não
    // monta a tela para quem não é staff.
    if (tutorStudentId != null && isStaff) {
      return <TutorStudentDetail studentId={tutorStudentId} onBack={() => changeView("tutor")} />;
    }
    // O leitor de OVA tem precedência sobre a aba ativa
    if (readerOva && session) {
      return (
        <OvaReader
          // AUDITORIA P3: remonta por OVA — zera o estado por-sessão do companheiro
          // (saudação/marcos) e do chat ao navegar de um módulo direto para outro
          // (deep-link #/modulo/:id) sem passar pela lista.
          key={readerOva.ova_id}
          ova={readerOva}
          studentId={session.student_id}
          persona={profile.estudante.persona}
          companionEnabled={profile.features?.companion ?? true}
          onBack={closeReader}
          onTracked={refreshProfile}
        />
      );
    }
    if (activeView === "contents") return <Contents profile={profile} onTracked={refreshProfile} onOpenOva={openOva} />;
    if (activeView === "exercises") return <Exercises profile={profile} onTracked={refreshProfile} />;
    if (activeView === "quiz") return <Quiz profile={profile} onTracked={refreshProfile} />;
    if (activeView === "reforco") return <Reforco profile={profile} onTracked={refreshProfile} />;
    if (activeView === "evolution") return <Evolution profile={profile} />;
    if (activeView === "tutor") return <TutorPanel />;
    if (activeView === "gestor" && isStaff) return <ManagerDashboard />;
    if (activeView === "report") return <Report profile={profile} onTracked={refreshProfile} />;
    return (
      <Dashboard
        profile={profile}
        onOpenContent={() => changeView("contents")}
        onOpenReforco={() => changeView("reforco")}
      />
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 text-ink">
      {/* NA.3 (Plano 4): pular para o conteúdo. preventDefault + foco programático
          para NÃO tocar no hash (o app usa hash-routing #/dashboard). */}
      <a
        href="#conteudo"
        onClick={(e) => {
          e.preventDefault();
          const el = document.getElementById("conteudo");
          el?.focus();
          el?.scrollIntoView();
        }}
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-[8px] focus:bg-brand focus:px-4 focus:py-2 focus:font-bold focus:text-white"
      >
        {t("Pular para o conteúdo", "Skip to content")}
      </a>
      {/* D.5 consentimento primeiro; U.5 onboarding logo depois. */}
      {needsConsent ? (
        <ConsentModal onDone={() => setNeedsConsent(false)} />
      ) : (
        needsOnboarding && (
          <OnboardingModal
            studentName={profile.estudante.nome}
            persona={profile.estudante.persona}
            onDone={() => setNeedsOnboarding(false)}
          />
        )
      )}
      <div className="flex">
        <Sidebar activeView={readerOva ? "contents" : activeView} onChangeView={changeView} studentName={profile.estudante.nome} role={profile.estudante.role} onLogout={logout} />
        <main id="conteudo" tabIndex={-1} className="min-w-0 flex-1 outline-none">
          <Topbar
            profile={profile}
            onChangeView={changeView}
            activeView={readerOva ? "contents" : activeView}
            studentName={profile.estudante.nome}
            role={profile.estudante.role}
            onLogout={logout}
          />
          <div className="mx-auto max-w-[1200px] px-5 py-8 lg:px-10">
            <Suspense fallback={<ViewFallback />}>{renderView()}</Suspense>
          </div>
        </main>
      </div>
    </div>
  );
};

export default App;
